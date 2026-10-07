"""Standalone M1 stages for preflight, transcription, planning, and compilation."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestrator.artifacts import write_json
from orchestrator.caption_renderers import SidecarOnlyRenderer, write_caption_review
from orchestrator.captions import CaptionConfig, build_captions
from orchestrator.cli import DryRunError, _load_settings, _workspace_path
from orchestrator.compiler import CompileConfig, compile_edl
from orchestrator.contracts import (
    check_captions,
    check_edl_against,
    check_ops,
    check_timeline,
    check_words,
    validate,
)
from orchestrator.metrics import real_time_factor
from orchestrator.packer import build_pack
from orchestrator.planner import BaselinePlanner, RecordedPlanner
from orchestrator.timeline import build_timeline
from perception.asr import AsrResult, AsrWord, WhisperXConfig, WhisperXEngine
from perception.audio import extract_audio_stream, hash_media_file, read_pcm16_mono
from perception.gaps import GapThresholds
from perception.preflight import MediaToolError, probe_media
from perception.speakers import (
    AudioTrack,
    apply_bleed_confidence,
    attribute_multitrack_words,
    build_speaker_report,
    ensure_unknown_speaker,
    expire_pending_questions,
    make_identify_question,
    rebuild_segments_by_speaker,
    select_speaker_mode,
    word_track_energies_from_wavs,
    write_wav_snippet,
)
from perception.words import build_words_document


def _new_output(value: str | Path | None, label: str) -> Path:
    default = (
        Path("runs")
        / f"{label}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    output = _workspace_path(value or default, "output directory")
    output.mkdir(parents=True, exist_ok=False)
    return output


def _load_speakers_document(settings: dict[str, Any]) -> dict[str, Any]:
    """Read only the configured speaker map; never inspect local secret config."""
    speaker_settings = settings.get("speakers", {})
    speaker_path = _workspace_path(speaker_settings.get("file", "speakers.json"), "speakers file")
    empty_document: dict[str, Any] = {
        "schema_version": "1.1.0",
        "speakers": {},
        "unknown_palette": ["#BDBDBD", "#CE93D8", "#A5D6A7"],
    }
    if not speaker_path.is_file():
        return empty_document
    try:
        document = json.loads(speaker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DryRunError("speaker map could not be read") from None
    if not isinstance(document, dict):
        raise DryRunError("speaker map has an invalid shape")
    if document.get("schema_version") == "1.0.0":
        document["schema_version"] = "1.1.0"
    if validate("speakers", document):
        raise DryRunError("speaker map failed contract validation")
    return document


def _audio_tracks(streams: list[Any], speakers_doc: dict[str, Any]) -> list[AudioTrack]:
    """Build deterministic stream IDs and human-facing mapping aliases."""
    tracks: list[AudioTrack] = []
    mixed_labels = {
        str(row.get("track", "")).casefold().strip()
        for row in speakers_doc.get("speakers", {}).values()
        if isinstance(row, dict) and row.get("track_mode") == "mixed"
    }
    for ordinal, stream in enumerate(streams):
        key = f"audio_{ordinal}"
        label = (
            stream.title.strip() if isinstance(stream.title, str) and stream.title.strip() else key
        )
        aliases = (f"Mic {ordinal + 1}", f"Track {ordinal + 1}", f"audio {ordinal}")
        mixed = label.casefold().strip() in mixed_labels or key.casefold() in mixed_labels
        tracks.append(AudioTrack(key, label, aliases, mixed))
    return tracks


def _has_pending_speaker_question(words_path: str | Path, *, now_epoch: float) -> bool:
    """Return whether a sibling ask_user artifact still blocks planning."""
    ask_path = Path(words_path).with_name("ask_user.json")
    if not ask_path.is_file():
        return False
    try:
        ask_user = json.loads(ask_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DryRunError("speaker identification status could not be read") from None
    if ask_user.get("status") != "awaiting_user":
        return False
    try:
        warnings = expire_pending_questions(
            ask_user,
            now_epoch=now_epoch,
            timeout_s=int(ask_user.get("timeout_s", 86400)),
        )
    except (TypeError, ValueError):
        raise DryRunError("speaker identification timeout metadata is invalid") from None
    if warnings:
        write_json(ask_path, ask_user)
    return ask_user.get("status") == "awaiting_user" and any(
        question.get("status") == "pending"
        for question in ask_user.get("questions", [])
        if isinstance(question, dict)
    )


def _unknown_words(words: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    for word in words:
        key = word.get("speaker")
        if isinstance(key, str) and key.startswith("unknown_") and key not in keys:
            keys.append(key)
    return keys


def run_transcribe(
    video_path: str | Path, *, max_seconds: int = 120, output_root: str | Path | None = None
) -> Path:
    """Run local preflight, audio extraction, and ASR, writing transcript artifacts."""
    if not 1 <= max_seconds <= 36000:
        raise DryRunError("maximum duration is outside the supported range")
    source = Path(video_path)
    before = hash_media_file(source)
    output = _new_output(output_root, "transcribe")
    start = time.perf_counter()
    try:
        probe = probe_media(source)
    except MediaToolError as error:
        write_json(
            output / "source_integrity.json",
            {"sha256_before": before, "sha256_after": hash_media_file(source)},
        )
        raise DryRunError(str(error)) from None
    timeline = build_timeline(probe, before, max_seconds=max_seconds)
    if validate("timeline", timeline) or check_timeline(timeline):
        raise DryRunError("timeline failed contract validation")
    write_json(output / "timeline.json", timeline)

    settings = _load_settings()
    speakers_doc = _load_speakers_document(settings)
    tracks = _audio_tracks(list(probe.audio_streams), speakers_doc)
    speaker_settings = settings.get("speakers", {})
    selection = select_speaker_mode(speaker_settings.get("mode", "single"), tracks, speakers_doc)
    if selection.mode in {"diarized", "hybrid"}:
        raise DryRunError("diarization requires an accepted local model backend; see RV-005")
    cache = _workspace_path(settings["paths"]["cache"], "cache")
    artifacts = [
        extract_audio_stream(source, stream.index, cache, duration_limit_s=max_seconds)
        for stream in probe.audio_streams
    ]
    if not artifacts:
        raise DryRunError("preflight found no audio stream")
    asr = settings["asr"]
    engine = WhisperXEngine(
        WhisperXConfig(
            model=asr["model"],
            device=asr["device"],
            compute_type=asr["compute_type"],
            language=asr["language"],
            model_cache_dir=cache / "asr_models",
        )
    )
    results: list[AsrResult] = []
    merged_words: list[AsrWord] = []
    gap_sources: list[tuple[AsrResult, str]] = []
    segment_offset = 0
    measurements = []
    duration_s = min(float(probe.duration or 0), float(max_seconds))
    for index, artifact in enumerate(artifacts):
        stage_start = time.perf_counter()
        result = engine.transcribe_aligned(artifact.path)
        elapsed = time.perf_counter() - stage_start
        results.append(result)
        measurements.append(
            {
                "stream_index": artifact.stream_index,
                "model": result.model,
                "align_model": result.align_model,
                "device": result.device,
                "compute_type": result.compute_type,
                "wall_clock_s": round(elapsed, 3),
                "real_time_factor": real_time_factor(elapsed, duration_s),
                "vram_gb": None,
                "fallback_reason": result.fallback_reason,
            }
        )
        gap_sources.append((result, str(artifact.path)))
        max_segment = max((word.segment_index for word in result.words), default=-1)
        merged_words.extend(
            replace(
                word, segment_index=word.segment_index + segment_offset, track=tracks[index].key
            )
            for word in result.words
        )
        segment_offset += max_segment + 1
    merged_words.sort(key=lambda word: (word.start is None, word.start or 0.0))
    primary = results[0]
    merged = replace(primary, words=tuple(merged_words))
    perception = settings["perception"]
    thresholds = GapThresholds(
        minimum_gap_ms=perception["gap_minimum_ms"],
        window_ms=perception["gap_window_ms"],
        noise_floor_multiplier=perception["gap_noise_floor_multiplier"],
        absolute_rms_floor=perception["gap_absolute_rms_floor"],
        minimum_quiet_ms=perception["gap_minimum_quiet_ms"],
    )
    words = build_words_document(
        merged,
        str(artifacts[0].path),
        before,
        timeline["fps"],
        speaker_mode=selection.mode,
        thresholds=thresholds,
        gap_sources=gap_sources,
    )
    if selection.mode == "multitrack":
        attribute_multitrack_words(words["words"], selection.track_speakers)
        energy_map = word_track_energies_from_wavs(
            words["words"],
            {track.key: artifacts[index].path for index, track in enumerate(tracks)},
        )
        bleed_reasons = apply_bleed_confidence(words["words"], energy_map)
    else:
        for word in words["words"]:
            word["speaker"] = "unknown_1"
            word["speaker_conf"] = 0.25
            word["overlap"] = False
        bleed_reasons = {}
    unknown_keys = _unknown_words(words["words"])
    for unknown_key in unknown_keys:
        ensure_unknown_speaker(speakers_doc, unknown_key)
    words["segments"] = rebuild_segments_by_speaker(words["words"])
    if validate("speakers", speakers_doc):
        raise DryRunError("speaker attribution output failed contract validation")
    speaker_report = build_speaker_report(words["words"], bleed_reasons)
    if validate("words", words) or check_words(words):
        raise DryRunError("ASR output failed words contract validation")
    write_json(output / "words.json", words)
    write_json(output / "speakers.json", speakers_doc)
    write_json(output / "speaker_report.json", speaker_report)
    if unknown_keys:
        questions: list[dict[str, Any]] = []
        for question_index, unknown_key in enumerate(unknown_keys, start=1):
            first_word = next(row for row in words["words"] if row.get("speaker") == unknown_key)
            track_key = (
                first_word.get("track")
                if isinstance(first_word.get("track"), str)
                else tracks[0].key
            )
            track_index = next((i for i, track in enumerate(tracks) if track.key == track_key), 0)
            samples, sample_rate = read_pcm16_mono(artifacts[track_index].path)
            start_s = (
                max(0.0, float(first_word["start"]) - 0.5)
                if isinstance(first_word.get("start"), int | float)
                else 0.0
            )
            end_s = min(len(samples) / sample_rate, start_s + 5.0)
            snippet = output / "ask_user" / f"{unknown_key}.wav"
            write_wav_snippet(samples, sample_rate, start_s, end_s, snippet)
            question = make_identify_question(
                f"identify_speaker_{question_index}",
                unknown_key,
                snippet.relative_to(output).as_posix(),
                speakers_doc,
            )
            question["status"] = "pending"
            questions.append(question)
        write_json(
            output / "ask_user.json",
            {
                "schema_version": "1.0.0",
                "status": "awaiting_user",
                "created_at_epoch": time.time(),
                "timeout_s": 86400,
                "questions": questions,
                "warnings": [],
            },
        )
    pack = build_pack(words)
    (output / "pack.txt").write_text(pack.text, encoding="utf-8")
    write_json(
        output / "asr_benchmark.json",
        {
            "schema_version": "1.0.0",
            "clip_duration_s": round(duration_s, 3),
            "streams": measurements,
        },
    )
    after = hash_media_file(source)
    write_json(
        output / "source_integrity.json",
        {
            "sha256_before": before,
            "sha256_after": after,
            "unchanged": before == after,
            "wall_clock_ms": round((time.perf_counter() - start) * 1000),
        },
    )
    if before != after:
        raise DryRunError("source integrity check failed")
    return output


def run_plan(
    words_path: str | Path,
    *,
    output_root: str | Path | None = None,
    recorded_edl: str | Path | None = None,
) -> Path:
    """Validate transcript input and write a baseline or recorded EDL."""
    try:
        words = json.loads(Path(words_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DryRunError("words input could not be read") from None
    if _has_pending_speaker_question(words_path, now_epoch=time.time()):
        raise DryRunError("speaker identification is pending; answer ask_user before planning")
    if not isinstance(words, dict) or validate("words", words) or check_words(words):
        raise DryRunError("words input failed contract validation")
    output = _new_output(output_root, "plan")
    pack = build_pack(words)
    (output / "pack.txt").write_text(pack.text, encoding="utf-8")
    catalog: dict[str, Any] = {
        "transitions": [],
        "video_fx": [],
        "audio_fx": [],
        "text_presets": [],
        "sfx": [],
    }
    planner = RecordedPlanner.from_file(recorded_edl) if recorded_edl else BaselinePlanner()
    edl = planner.plan(pack.text, words, catalog)
    speakers_path = Path(words_path).with_name("speakers.json")
    speakers_doc: dict[str, Any] = {"speakers": {}}
    if speakers_path.is_file():
        try:
            loaded_speakers = json.loads(speakers_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise DryRunError("speaker map could not be read") from None
        if not isinstance(loaded_speakers, dict) or validate("speakers", loaded_speakers):
            raise DryRunError("speaker map failed contract validation")
        speakers_doc = loaded_speakers
    if validate("edl", edl) or check_edl_against(edl, words, speakers_doc, catalog):
        raise DryRunError("planner output failed EDL validation")
    write_json(output / "edl.json", edl)
    return output


def run_compile(
    words_path: str | Path,
    timeline_path: str | Path,
    edl_path: str | Path,
    *,
    output_root: str | Path | None = None,
    audio_path: str | Path | None = None,
    speakers_path: str | Path | None = None,
) -> Path:
    """Validate inputs and write frame-resolved ops and caption sidecars."""
    try:
        words = json.loads(Path(words_path).read_text(encoding="utf-8"))
        timeline = json.loads(Path(timeline_path).read_text(encoding="utf-8"))
        edl = json.loads(Path(edl_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DryRunError("compile input could not be read") from None
    if _has_pending_speaker_question(words_path, now_epoch=time.time()):
        raise DryRunError("speaker identification is pending; answer ask_user before compilation")
    if not all(isinstance(item, dict) for item in (words, timeline, edl)):
        raise DryRunError("compile input has an invalid shape")
    if (
        validate("words", words)
        or check_words(words)
        or validate("timeline", timeline)
        or check_timeline(timeline)
    ):
        raise DryRunError("words or timeline input failed contract validation")
    speaker_file = (
        Path(speakers_path)
        if speakers_path is not None
        else Path(words_path).with_name("speakers.json")
    )
    try:
        speakers_doc = json.loads(speaker_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DryRunError(
            "speaker map could not be read; supply --speakers or place it beside words.json"
        ) from None
    if not isinstance(speakers_doc, dict) or validate("speakers", speakers_doc):
        raise DryRunError("speaker map failed contract validation")
    catalog: dict[str, Any] = {
        "transitions": [],
        "video_fx": [],
        "audio_fx": [],
        "text_presets": [],
        "sfx": [],
    }
    if validate("edl", edl) or check_edl_against(edl, words, speakers_doc, catalog, timeline):
        raise DryRunError("EDL input failed schema or referential validation")
    output = _new_output(output_root, "compile")
    settings = _load_settings()
    compile_settings = settings["compile"]
    caption_config = CaptionConfig.from_mapping(settings.get("subtitles", {}))
    caption_config.validate()
    config = CompileConfig(
        head_pad_ms=compile_settings["head_pad_ms"],
        tail_pad_ms=compile_settings["tail_pad_ms"],
        min_gap_after_cut_ms=compile_settings["min_gap_after_cut_ms"],
        audio_crossfade_ms=compile_settings["audio_crossfade_ms"],
        max_removed_percent=compile_settings["max_removed_percent"],
        snap_zero_crossing=compile_settings["snap_zero_crossing"],
    )
    audio_samples = None
    sample_rate = None
    if audio_path is not None:
        safe_audio_path = _workspace_path(audio_path, "audio analysis file")
        audio_samples, sample_rate = read_pcm16_mono(safe_audio_path)
    ops, report, removed = compile_edl(
        edl,
        words,
        timeline,
        job_id=output.name,
        working_copy_path=str(output / "working_copy_placeholder.veg"),
        config=config,
        audio_samples=audio_samples,
        sample_rate=sample_rate,
    )
    caption_document, caption_report = build_captions(
        words,
        edl,
        timeline,
        removed,
        config=caption_config,
        speakers_document=speakers_doc,
    )
    if (
        validate("ops", ops)
        or check_ops(ops, output)
        or validate("compile_report", report)
        or validate("captions", caption_document)
        or check_captions(caption_document, words)
    ):
        raise DryRunError("compiler or caption output failed contract validation")
    write_json(output / "ops.json", ops)
    write_json(output / "compile_report.json", report)
    SidecarOnlyRenderer().write_sidecars(
        output, caption_document, caption_report, speakers_doc, caption_config
    )
    write_caption_review(output / "review.md", caption_report)
    return output
