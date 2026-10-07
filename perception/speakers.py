"""Deterministic speaker attribution helpers with injectable local model interfaces.

The module contains no network client and never loads a checkpoint. Real inference adapters
must be supplied only after the local model and its terms have been accepted.
"""

from __future__ import annotations

import json
import math
import re
import statistics
import wave
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

SpeakerMode = Literal["auto", "single", "multitrack", "diarized", "hybrid"]
_UNKNOWN_KEY = re.compile(r"^unknown_([1-9][0-9]*)$")
_SPEAKER_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


class SpeakerError(ValueError):
    """A safe speaker-stage failure without transcript or credential contents."""


class EnrollmentError(SpeakerError):
    """An enrollment sample failed quality checks or lacks a local encoder."""


@dataclass(frozen=True, slots=True)
class AudioTrack:
    """One normalized mono audio stream and its user-visible mapping labels."""

    key: str
    label: str
    aliases: tuple[str, ...] = ()
    mixed: bool = False


@dataclass(frozen=True, slots=True)
class DiarizationTurn:
    """A model-provided speaker turn; model inference is outside this module."""

    cluster: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class ModeSelection:
    mode: Literal["single", "multitrack", "diarized", "hybrid"]
    track_speakers: dict[str, str]
    mixed_tracks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EnrollmentResult:
    embedding: tuple[float, ...]
    model: str
    sample_duration_s: float
    snr_db: float


class SpeakerEmbeddingEngine(Protocol):
    """Local-only interface for a model that emits speaker embeddings."""

    model_id: str

    def encode(self, samples: Sequence[int], sample_rate_hz: int) -> Sequence[float]:
        """Return a finite, nonzero speaker embedding for one audio window."""


class DiarizationEngine(Protocol):
    """Local-only interface for a diarizer that returns time-bounded speaker turns."""

    model_id: str

    def diarize(self, samples: Sequence[int], sample_rate_hz: int) -> Sequence[DiarizationTurn]:
        """Return turns without writing audio or sending it to a remote service."""


def _normalized_label(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _track_mapping(speakers_doc: dict[str, Any], tracks: Sequence[AudioTrack]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for track in tracks:
        for value in (track.key, track.label, *track.aliases):
            aliases[_normalized_label(value)] = track.key
    mapped: dict[str, str] = {}
    for speaker_key, speaker in speakers_doc.get("speakers", {}).items():
        if not isinstance(speaker, dict):
            continue
        source = speaker.get("track")
        if not isinstance(source, str):
            continue
        track_key = aliases.get(_normalized_label(source))
        if track_key is not None:
            mapped[track_key] = speaker_key
    return mapped


def select_speaker_mode(
    requested: SpeakerMode,
    tracks: Sequence[AudioTrack],
    speakers_doc: dict[str, Any],
) -> ModeSelection:
    """Choose a mode from explicit per-track mappings, preserving configured overrides."""
    if not tracks:
        raise SpeakerError("speaker mode selection requires an audio stream")
    track_speakers = _track_mapping(speakers_doc, tracks)
    mixed_keys = {track.key for track in tracks if track.mixed}
    for track_key, speaker_key in track_speakers.items():
        speaker = speakers_doc.get("speakers", {}).get(speaker_key)
        if isinstance(speaker, dict) and speaker.get("track_mode") == "mixed":
            mixed_keys.add(track_key)
    mixed_tracks = tuple(track.key for track in tracks if track.key in mixed_keys)
    if requested != "auto":
        return ModeSelection(requested, track_speakers, mixed_tracks)

    mapped_keys = set(track_speakers)
    has_unmapped = any(track.key not in mapped_keys for track in tracks)
    has_mixed = bool(mixed_tracks)
    if mapped_keys and (has_mixed or has_unmapped):
        mode: Literal["single", "multitrack", "diarized", "hybrid"] = "hybrid"
    elif has_mixed or has_unmapped and len(tracks) > 1:
        mode = "diarized"
    elif mapped_keys and not has_unmapped:
        mode = "multitrack"
    elif len(tracks) == 1 and len(speakers_doc.get("speakers", {})) > 1:
        mode = "diarized"
    elif len(tracks) == 1:
        mode = "single"
    else:
        mode = "diarized"
    return ModeSelection(mode, track_speakers, mixed_tracks)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return cosine similarity, rejecting malformed vectors instead of guessing."""
    if len(left) == 0 or len(left) != len(right):
        raise SpeakerError("speaker embeddings have incompatible dimensions")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not math.isfinite(left_norm * right_norm) or left_norm == 0 or right_norm == 0:
        raise SpeakerError("speaker embedding is invalid")
    score = sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
    if not math.isfinite(score):
        raise SpeakerError("speaker similarity is invalid")
    return max(-1.0, min(1.0, score))


def match_embedding(
    embedding: Sequence[float],
    profiles: dict[str, Sequence[float]],
    *,
    threshold: float,
    ambiguity_margin: float = 0.03,
) -> tuple[str | None, float]:
    """Match only above threshold and outside the near-tie margin; otherwise stay unknown."""
    if not 0 <= threshold <= 1 or not 0 <= ambiguity_margin <= 1:
        raise SpeakerError("speaker similarity settings are invalid")
    ranked = sorted(
        ((key, cosine_similarity(embedding, value)) for key, value in profiles.items()),
        key=lambda item: (-item[1], item[0]),
    )
    if not ranked:
        return None, 0.0
    if ranked[0][1] < threshold:
        return None, ranked[0][1]
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < ambiguity_margin:
        return None, ranked[0][1]
    return ranked[0]


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, value if math.isfinite(value) else 0.0))


def attribute_words_from_turns(
    words: list[dict[str, Any]],
    turns: Sequence[DiarizationTurn],
    cluster_speakers: dict[str, str],
    *,
    overlap_confidence_multiplier: float = 0.5,
) -> None:
    """Assign by timed overlap; mark overlapping words and lower their confidence."""
    if not 0 <= overlap_confidence_multiplier <= 1:
        raise SpeakerError("overlap confidence setting is invalid")
    cluster_order: dict[str, str] = {}
    for word in words:
        start, end = word.get("start"), word.get("end")
        if not isinstance(start, int | float) or not isinstance(end, int | float) or end <= start:
            word["speaker"] = None
            word["speaker_conf"] = 0.0
            word["overlap"] = False
            continue
        duration = float(end) - float(start)
        overlaps: dict[str, tuple[float, float]] = {}
        for turn in turns:
            if (
                not math.isfinite(turn.start)
                or not math.isfinite(turn.end)
                or turn.end <= turn.start
            ):
                continue
            intersection = max(0.0, min(float(end), turn.end) - max(float(start), turn.start))
            if intersection <= 0:
                continue
            prior = overlaps.get(turn.cluster, (0.0, 0.0))
            overlaps[turn.cluster] = (
                prior[0] + intersection,
                max(prior[1], _clamp_confidence(turn.confidence)),
            )
        if not overlaps:
            word["speaker"] = None
            word["speaker_conf"] = 0.0
            word["overlap"] = False
            continue
        ordered = sorted(overlaps.items(), key=lambda item: (-item[1][0], item[0]))
        cluster, (covered, turn_confidence) = ordered[0]
        if cluster not in cluster_speakers:
            cluster_order.setdefault(cluster, f"unknown_{len(cluster_order) + 1}")
        word["speaker"] = (
            cluster_speakers[cluster] if cluster in cluster_speakers else cluster_order[cluster]
        )
        word["overlap"] = len(overlaps) > 1
        confidence = _clamp_confidence(min(1.0, covered / duration) * turn_confidence)
        if word["overlap"]:
            confidence *= overlap_confidence_multiplier
        word["speaker_conf"] = _clamp_confidence(confidence)


def attribute_multitrack_words(
    words: list[dict[str, Any]],
    track_speakers: dict[str, str],
    *,
    base_confidence: float = 1.0,
) -> None:
    """Label words from their mapped source track; unmapped tracks remain named unknowns."""
    if not 0 <= base_confidence <= 1:
        raise SpeakerError("track attribution confidence is invalid")
    unknown_by_track: dict[str, str] = {}
    for word in words:
        track = word.get("track")
        if not isinstance(track, str):
            word["speaker"] = None
            word["speaker_conf"] = 0.0
            word["overlap"] = False
            continue
        if track not in track_speakers:
            unknown_by_track.setdefault(track, f"unknown_{len(unknown_by_track) + 1}")
        word["speaker"] = (
            track_speakers[track] if track in track_speakers else unknown_by_track[track]
        )
        word["speaker_conf"] = base_confidence if track in track_speakers else 0.25
        word["overlap"] = False


def frame_rms(samples: Sequence[int], sample_rate_hz: int, *, frame_ms: int = 20) -> list[float]:
    """Calculate fixed-width PCM frame RMS values in one pass."""
    if sample_rate_hz <= 0 or frame_ms <= 0:
        raise SpeakerError("audio analysis settings are invalid")
    width = max(1, sample_rate_hz * frame_ms // 1000)
    levels: list[float] = []
    for offset in range(0, len(samples), width):
        frame = samples[offset : offset + width]
        if frame:
            levels.append(
                math.sqrt(sum(float(value) * float(value) for value in frame) / len(frame))
            )
    return levels


def word_track_energies(
    words: Sequence[dict[str, Any]],
    samples_by_track: dict[str, Sequence[int]],
    sample_rate_hz: int,
    *,
    frame_ms: int = 20,
) -> dict[str, dict[str, float]]:
    """Measure approximate frame RMS for each aligned word on every audio track."""
    width_s = frame_ms / 1000
    levels_by_track = {
        track: frame_rms(samples, sample_rate_hz, frame_ms=frame_ms)
        for track, samples in samples_by_track.items()
    }
    result: dict[str, dict[str, float]] = {}
    for word in words:
        word_id, start, end = word.get("id"), word.get("start"), word.get("end")
        if (
            not isinstance(word_id, str)
            or not isinstance(start, int | float)
            or not isinstance(end, int | float)
            or end <= start
        ):
            continue
        first = max(0, int(float(start) / width_s))
        last = max(first + 1, math.ceil(float(end) / width_s))
        per_track: dict[str, float] = {}
        for track, levels in levels_by_track.items():
            window = levels[first:last]
            per_track[track] = statistics.fmean(window) if window else 0.0
        result[word_id] = per_track
    return result


def apply_bleed_confidence(
    words: list[dict[str, Any]],
    energies: dict[str, dict[str, float]],
    *,
    likely_bleed_ratio: float = 0.2,
    ambiguous_bleed_ratio: float = 0.55,
) -> dict[str, str]:
    """Keep competing text, but lower confidence when a source track has weak relative energy."""
    if not 0 <= likely_bleed_ratio <= ambiguous_bleed_ratio <= 1:
        raise SpeakerError("bleed comparison settings are invalid")
    reasons: dict[str, str] = {}
    by_token: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for word in words:
        token = "".join(char.casefold() for char in str(word.get("text", "")) if char.isalnum())
        if token and word.get("alignment_status", "aligned") != "unaligned":
            by_token[token].append(word)
    for candidates in by_token.values():
        candidates.sort(key=lambda row: (float(row.get("start", 0)), str(row.get("track", ""))))
        for index, word in enumerate(candidates):
            start, end, word_id = word.get("start"), word.get("end"), word.get("id")
            if (
                not isinstance(start, int | float)
                or not isinstance(end, int | float)
                or end <= start
            ):
                continue
            for other in candidates[index + 1 :]:
                other_start, other_end = other.get("start"), other.get("end")
                if not isinstance(other_start, int | float) or not isinstance(
                    other_end, int | float
                ):
                    continue
                if other_start >= end:
                    break
                if other.get("track") == word.get("track") or other_end <= start:
                    continue
                other_id = other.get("id")
                if not isinstance(word_id, str) or not isinstance(other_id, str):
                    continue
                first = energies.get(word_id, {}).get(str(word.get("track", "")), 0.0)
                second = energies.get(other_id, {}).get(str(other.get("track", "")), 0.0)
                high = max(first, second)
                if high <= 0:
                    continue
                low_ratio = min(first, second) / high
                if low_ratio <= likely_bleed_ratio:
                    low_word = word if first <= second else other
                    low_id = word_id if first <= second else other_id
                    low_word["speaker_conf"] = min(float(low_word.get("speaker_conf", 0.0)), 0.2)
                    reasons[low_id] = "likely_track_bleed"
                elif low_ratio <= ambiguous_bleed_ratio:
                    low_word = word if first <= second else other
                    low_id = word_id if first <= second else other_id
                    low_word["speaker_conf"] = min(float(low_word.get("speaker_conf", 0.0)), 0.45)
                    reasons[low_id] = "ambiguous_track_bleed"
    return reasons


def build_speaker_report(
    words: Sequence[dict[str, Any]],
    reasons: dict[str, str] | None = None,
    *,
    low_confidence_threshold: float = 0.65,
) -> dict[str, Any]:
    """Create path-free, transcript-free ranges requiring human attribution review."""
    if not 0 <= low_confidence_threshold <= 1:
        raise SpeakerError("speaker report threshold is invalid")
    reason_by_id = reasons or {}
    rows: list[dict[str, Any]] = []
    for word in words:
        confidence = word.get("speaker_conf", 0.0)
        if not isinstance(confidence, int | float) or confidence >= low_confidence_threshold:
            continue
        word_id = word.get("id")
        reason = reason_by_id.get(str(word_id))
        if reason is None:
            reason = (
                "overlapping_turns"
                if word.get("overlap")
                else (
                    "speaker_unassigned"
                    if word.get("speaker") is None
                    else "low_speaker_confidence"
                )
            )
        rows.append(
            {
                "word_id": word_id,
                "start": word.get("start"),
                "end": word.get("end"),
                "speaker": word.get("speaker"),
                "speaker_conf": confidence,
                "reason": reason,
            }
        )
    return {
        "schema_version": "1.0.0",
        "low_confidence_threshold": low_confidence_threshold,
        "low_confidence_count": len(rows),
        "ranges": rows,
    }


def rebuild_segments_by_speaker(words: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split contiguous phrase segments whenever attribution or overlap status changes."""
    segments: list[dict[str, Any]] = []
    current_key: tuple[str | None, bool] | None = None
    current_ids: list[str] = []
    for word in words:
        word_id = word.get("id")
        if not isinstance(word_id, str):
            continue
        speaker = word.get("speaker") if isinstance(word.get("speaker"), str) else None
        overlap = bool(word.get("overlap", False))
        key = (speaker, overlap)
        if current_ids and current_key is not None and key != current_key:
            segments.append(
                {"id": f"s{len(segments) + 1}", "word_ids": current_ids, "speaker": current_key[0]}
            )
            current_ids = []
        current_key = key
        current_ids.append(word_id)
    if current_ids and current_key is not None:
        segments.append(
            {"id": f"s{len(segments) + 1}", "word_ids": current_ids, "speaker": current_key[0]}
        )
    return segments


def ensure_unknown_speaker(speakers_doc: dict[str, Any], key: str) -> None:
    """Add a palette-backed unknown entry without replacing a human-defined key."""
    match = _UNKNOWN_KEY.fullmatch(key)
    if match is None:
        raise SpeakerError("unknown speaker key is invalid")
    if key in speakers_doc.setdefault("speakers", {}):
        return
    number = int(match.group(1))
    palette = speakers_doc.get("unknown_palette")
    if not isinstance(palette, list) or not palette:
        palette = ["#BDBDBD"]
        speakers_doc["unknown_palette"] = palette
    color = palette[(number - 1) % len(palette)]
    speakers_doc["speakers"][key] = {"display": f"Unknown {number}", "color": color}
    speakers_doc["schema_version"] = "1.1.0"


def make_identify_question(
    question_id: str,
    speaker_key: str,
    snippet_path: str,
    speakers_doc: dict[str, Any],
) -> dict[str, Any]:
    """Create the typed CLI ask_user payload; names are display-only suggestions."""
    if _UNKNOWN_KEY.fullmatch(speaker_key) is None:
        raise SpeakerError("identification question requires an unknown speaker key")
    candidates = [
        row["display"]
        for row in speakers_doc.get("speakers", {}).values()
        if isinstance(row, dict)
        and isinstance(row.get("display"), str)
        and not _UNKNOWN_KEY.fullmatch(str(row.get("display", "")).casefold().replace(" ", "_"))
    ][:3]
    return {
        "id": question_id,
        "type": "identify_speaker",
        "speaker_key": speaker_key,
        "snippet_path": snippet_path,
        "candidate_names": candidates,
        "free_text_allowed": True,
    }


def _speaker_key_from_name(name: str, speakers_doc: dict[str, Any]) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    if not cleaned:
        raise SpeakerError("speaker name must contain a letter or number")
    if cleaned[0].isdigit():
        cleaned = "speaker_" + cleaned
    candidate = cleaned[:80]
    if not _SPEAKER_KEY.fullmatch(candidate):
        raise SpeakerError("speaker name cannot form a valid speaker key")
    existing = speakers_doc.get("speakers", {})
    if candidate not in existing:
        return candidate
    index = 2
    while f"{candidate}_{index}" in existing:
        index += 1
    return f"{candidate}_{index}"


def apply_identification_answer(
    speakers_doc: dict[str, Any],
    words_doc: dict[str, Any],
    speaker_key: str,
    display_name: str,
) -> dict[str, Any]:
    """Return a confirmed-change description while preserving confidence and track identity."""
    unknown_match = _UNKNOWN_KEY.fullmatch(speaker_key)
    if unknown_match is None or not display_name.strip():
        raise SpeakerError("speaker identification answer is invalid")
    current_speakers = speakers_doc.get("speakers", {})
    if speaker_key not in current_speakers:
        raise SpeakerError("unknown speaker entry is missing")
    existing_key = next(
        (
            key
            for key, row in current_speakers.items()
            if isinstance(row, dict)
            and str(row.get("display", "")).casefold() == display_name.strip().casefold()
            and key != speaker_key
        ),
        None,
    )
    new_key = existing_key or _speaker_key_from_name(display_name, speakers_doc)
    target_words = [
        word
        for word in words_doc.get("words", [])
        if isinstance(word, dict) and word.get("speaker") == speaker_key
    ]
    target_tracks = {
        word.get("track") for word in target_words if isinstance(word.get("track"), str)
    }
    mapped_track: str | None = None
    if words_doc.get("speaker_mode") in {"single", "multitrack"} and len(target_tracks) == 1:
        mapped_track = str(next(iter(target_tracks)))
    if existing_key is None:
        entry = dict(current_speakers[speaker_key])
        entry["display"] = display_name.strip()[:80]
        entry.pop("voice_profile", None)
        entry.pop("voice_profile_metadata", None)
        if mapped_track is not None:
            entry["track"] = mapped_track
            entry["track_mode"] = "single_speaker"
        current_speakers[new_key] = entry
    elif mapped_track is not None:
        entry = current_speakers.get(existing_key)
        if isinstance(entry, dict) and not entry.get("track"):
            entry["track"] = mapped_track
            entry["track_mode"] = "single_speaker"
    del current_speakers[speaker_key]
    reassigned_word_count = 0
    for word in target_words:
        word["speaker"] = new_key
        reassigned_word_count += 1
    words_doc["segments"] = rebuild_segments_by_speaker(words_doc.get("words", []))
    return {
        "speaker_key_before": speaker_key,
        "speaker_key_after": new_key,
        "display_before": f"Unknown {unknown_match.group(1)}",
        "display_after": display_name.strip()[:80],
        "track_after": mapped_track,
        "reassigned_word_count": reassigned_word_count,
    }


def _sample_rms_levels(
    samples: Sequence[int], sample_rate_hz: int, window_ms: int = 20
) -> list[float]:
    width = max(1, sample_rate_hz * window_ms // 1000)
    levels: list[float] = []
    for offset in range(0, len(samples), width):
        chunk = samples[offset : offset + width]
        if chunk:
            levels.append(
                math.sqrt(sum(float(value) * float(value) for value in chunk) / len(chunk))
            )
    return levels


def _normalized_embedding(values: Sequence[float]) -> tuple[float, ...]:
    vector = tuple(float(value) for value in values)
    if not vector or any(not math.isfinite(value) for value in vector):
        raise EnrollmentError("speaker encoder returned an invalid embedding")
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0 or not math.isfinite(norm):
        raise EnrollmentError("speaker encoder returned an empty embedding")
    return tuple(value / norm for value in vector)


def enroll_samples(
    samples: Sequence[int],
    sample_rate_hz: int,
    engine: SpeakerEmbeddingEngine,
    *,
    minimum_duration_s: float = 3.0,
    minimum_snr_db: float = 10.0,
    minimum_segment_similarity: float = 0.82,
) -> EnrollmentResult:
    """Validate an approved local sample and store only a normalized embedding."""
    if sample_rate_hz != 16000:
        raise EnrollmentError("enrollment audio must be 16 kHz mono PCM")
    duration = len(samples) / sample_rate_hz
    if duration < minimum_duration_s:
        raise EnrollmentError("enrollment sample is too short")
    if duration > 600:
        raise EnrollmentError("enrollment sample exceeds the 10-minute limit")
    levels = _sample_rms_levels(samples, sample_rate_hz)
    if not levels or max(levels) <= 0:
        raise EnrollmentError("enrollment sample contains no speech-level audio")
    ordered = sorted(levels)
    noise = statistics.median(ordered[: max(1, math.ceil(len(ordered) * 0.1))])
    speech = statistics.quantiles(ordered, n=10)[-1] if len(ordered) >= 10 else max(ordered)
    snr_db = 20 * math.log10(max(speech, 1.0) / max(noise, 1.0))
    if snr_db < minimum_snr_db:
        raise EnrollmentError("enrollment sample signal-to-noise ratio is too low")

    segment_size = sample_rate_hz
    vectors = [
        _normalized_embedding(
            engine.encode(samples[offset : offset + segment_size], sample_rate_hz)
        )
        for offset in range(0, len(samples), segment_size)
        if len(samples[offset : offset + segment_size]) >= sample_rate_hz // 2
    ]
    if len(vectors) < 2:
        raise EnrollmentError("enrollment sample has too few analyzable speech windows")
    centroid = _normalized_embedding(
        [statistics.fmean(vector[index] for vector in vectors) for index in range(len(vectors[0]))]
    )
    if any(len(vector) != len(centroid) for vector in vectors):
        raise EnrollmentError("speaker encoder changed embedding dimensions")
    if min(cosine_similarity(vector, centroid) for vector in vectors) < minimum_segment_similarity:
        raise EnrollmentError(
            "enrollment sample appears to contain multiple speakers or unstable audio"
        )
    return EnrollmentResult(centroid, engine.model_id, duration, snr_db)


def save_voice_profile(
    path: str | Path, result: EnrollmentResult, *, voices_root: str | Path = "voices"
) -> Path:
    """Write a JSON embedding under the ignored voices directory, never raw audio."""
    root = Path(voices_root).resolve()
    target = Path(path)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    if not target.is_relative_to(root) or target.suffix.lower() != ".json":
        raise SpeakerError("voice profile must be a JSON embedding inside the voices directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "model": result.model,
        "embedding": list(result.embedding),
        "sample_duration_s": round(result.sample_duration_s, 3),
        "sample_rate_hz": 16000,
        "snr_db": round(result.snr_db, 2),
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def read_embedding_profile(path: str | Path) -> tuple[str, tuple[float, ...]]:
    """Read and validate a local JSON embedding profile."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SpeakerError("voice profile could not be read") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("embedding"), list):
        raise SpeakerError("voice profile has an invalid shape")
    model = payload.get("model")
    if not isinstance(model, str):
        raise SpeakerError("voice profile has an invalid model identifier")
    return model, _normalized_embedding(payload["embedding"])


def read_pcm16_wav(path: str | Path) -> tuple[list[int], int]:
    """Read an approved local mono PCM16 WAV for enrollment."""
    try:
        with wave.open(str(path), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2:
                raise EnrollmentError("enrollment audio must be mono PCM16 WAV")
            sample_rate = source.getframerate()
            raw = source.readframes(source.getnframes())
    except (OSError, wave.Error):
        raise EnrollmentError("enrollment WAV could not be read") from None
    if sample_rate != 16000 or len(raw) % 2:
        raise EnrollmentError("enrollment audio must be 16 kHz mono PCM16 WAV")
    values = [
        int.from_bytes(raw[offset : offset + 2], "little", signed=True)
        for offset in range(0, len(raw), 2)
    ]
    return values, sample_rate


def write_wav_snippet(
    samples: Sequence[int], sample_rate_hz: int, start_s: float, end_s: float, path: str | Path
) -> Path:
    """Write a short mono PCM16 identification snippet inside the run folder."""
    if sample_rate_hz <= 0 or end_s <= start_s or end_s - start_s > 8.0:
        raise SpeakerError("identification snippet bounds are invalid")
    first = max(0, int(start_s * sample_rate_hz))
    last = min(len(samples), math.ceil(end_s * sample_rate_hz))
    if last <= first:
        raise SpeakerError("identification snippet is empty")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate_hz)
        raw = bytearray()
        for value in samples[first:last]:
            clipped = max(-32768, min(32767, int(value)))
            raw.extend(clipped.to_bytes(2, "little", signed=True))
        output.writeframes(bytes(raw))
    return target


def word_track_energies_from_wavs(
    words: Sequence[dict[str, Any]],
    wavs_by_track: dict[str, str | Path],
    *,
    frame_ms: int = 20,
) -> dict[str, dict[str, float]]:
    """Measure word-window RMS from WAV files while retaining only frame summaries."""
    from array import array

    if frame_ms <= 0:
        raise SpeakerError("bleed frame width must be positive")
    levels_by_track: dict[str, list[float]] = {}
    rates: set[int] = set()
    for track, wav_path in wavs_by_track.items():
        levels: list[float] = []
        try:
            with wave.open(str(wav_path), "rb") as source:
                if source.getnchannels() != 1 or source.getsampwidth() != 2:
                    raise SpeakerError("bleed analysis requires mono PCM16 WAV")
                sample_rate = source.getframerate()
                rates.add(sample_rate)
                width = max(1, sample_rate * frame_ms // 1000)
                while True:
                    raw = source.readframes(width)
                    if not raw:
                        break
                    samples = array("h")
                    samples.frombytes(raw)
                    if samples:
                        levels.append(
                            math.sqrt(sum(value * value for value in samples) / len(samples))
                        )
        except (OSError, wave.Error):
            raise SpeakerError("bleed analysis WAV could not be read") from None
        levels_by_track[track] = levels
    if len(rates) > 1:
        raise SpeakerError("bleed analysis WAV sample rates differ")
    sample_rate = next(iter(rates), 0)
    if sample_rate <= 0:
        return {}
    width_s = frame_ms / 1000
    result: dict[str, dict[str, float]] = {}
    for word in words:
        word_id, start, end = word.get("id"), word.get("start"), word.get("end")
        if (
            not isinstance(word_id, str)
            or not isinstance(start, int | float)
            or not isinstance(end, int | float)
            or end <= start
        ):
            continue
        first = max(0, int(float(start) / width_s))
        last = max(first + 1, math.ceil(float(end) / width_s))
        result[word_id] = {
            track: statistics.fmean(levels[first:last]) if levels[first:last] else 0.0
            for track, levels in levels_by_track.items()
        }
    return result


def expire_identification_question(question: dict[str, Any]) -> dict[str, Any]:
    """Record the timeout outcome while preserving the original unknown identity."""
    key = question.get("speaker_key")
    match = _UNKNOWN_KEY.fullmatch(key) if isinstance(key, str) else None
    if question.get("type") != "identify_speaker" or match is None:
        raise SpeakerError("identification question is invalid")
    number = match.group(1)
    return {
        "id": question.get("id"),
        "status": "timed_out",
        "speaker_key": key,
        "warning": f"Identification timed out; retained Unknown {number}.",
    }


def update_enrollment_metadata(
    speakers_doc: dict[str, Any],
    speaker_key: str,
    profile_path: str | Path,
    result: EnrollmentResult,
    *,
    quality_status: Literal["passed", "assumed"] = "assumed",
) -> None:
    """Attach embedding-only metadata to an existing speaker entry."""
    if not _SPEAKER_KEY.fullmatch(speaker_key):
        raise SpeakerError("speaker key is invalid")
    speaker = speakers_doc.get("speakers", {}).get(speaker_key)
    if not isinstance(speaker, dict):
        raise SpeakerError("speaker entry is missing")
    relative = Path(profile_path).as_posix()
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise SpeakerError("voice profile reference must be relative")
    speaker["voice_profile"] = relative
    speaker["voice_profile_metadata"] = {
        "model": result.model[:160],
        "embedding_dim": len(result.embedding),
        "sample_rate_hz": 16000,
        "sample_duration_s": round(result.sample_duration_s, 3),
        "quality_status": quality_status,
    }
    speakers_doc["schema_version"] = "1.1.0"


def expire_pending_questions(
    questions_doc: dict[str, Any], *, now_epoch: float, timeout_s: int = 86400
) -> list[dict[str, Any]]:
    """Mark expired questions with Unknown warnings using an injected clock value."""
    created = questions_doc.get("created_at_epoch")
    if (
        not isinstance(created, int | float)
        or not math.isfinite(float(created))
        or not isinstance(now_epoch, int | float)
        or not math.isfinite(float(now_epoch))
        or timeout_s < 1
    ):
        raise SpeakerError("identification timeout metadata is invalid")
    if float(now_epoch) - float(created) < timeout_s:
        return []
    warnings: list[dict[str, Any]] = []
    for question in questions_doc.get("questions", []):
        if isinstance(question, dict) and question.get("status", "pending") == "pending":
            expired = expire_identification_question(question)
            question["status"] = "timed_out"
            warnings.append(expired)
    if questions_doc.get("questions") and all(
        isinstance(question, dict) and question.get("status") in {"answered", "timed_out"}
        for question in questions_doc["questions"]
    ):
        questions_doc["status"] = (
            "timed_out"
            if any(row.get("status") == "timed_out" for row in questions_doc["questions"])
            else "answered"
        )
    questions_doc.setdefault("warnings", []).extend(warnings)
    return warnings
