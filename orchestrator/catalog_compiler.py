"""Pure, fail-closed policies for optional catalog-backed planner items."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from orchestrator.capabilities import empty_capabilities, supported_operations


@dataclass(frozen=True, slots=True)
class CatalogPlacementConfig:
    minimum_transition_frames: int = 2
    maximum_transition_frames: int = 48
    transitions_per_minute: int = 6
    sfx_per_minute: int = 6
    target_sfx_loudness_lufs: float = -24.0
    maximum_sfx_gain_db: float = 0.0
    maximum_sfx_peak_dbfs: float = -1.0
    minimum_sfx_gain_db: float = -60.0
    avoid_speech_peaks: bool = True
    speech_peak_threshold_dbfs: float = -12.0
    speech_peak_window_ms: int = 20
    placement_search_window_frames: int = 12
    allow_sfx_overlap: bool = False
    allow_non_dialogue_safe_continuous: bool = False
    continuous_speech_gap_ms: int = 250


@dataclass(frozen=True, slots=True)
class CatalogPlacementResult:
    operations: list[dict[str, Any]]
    item_outcomes: list[dict[str, Any]]
    rejected_items: list[dict[str, str]]
    warnings: list[dict[str, str]]
    sfx_used: list[dict[str, str]]


def resolved_transition_duration(entry: Mapping[str, Any], config: CatalogPlacementConfig) -> int:
    """Clamp only the catalog default to configured integer-frame bounds."""
    value = entry.get("default_duration_frames")
    if type(value) is not int or value < 1:
        raise ValueError("catalog transition duration is invalid")
    if (
        config.minimum_transition_frames < 1
        or config.maximum_transition_frames < config.minimum_transition_frames
    ):
        raise ValueError("transition duration policy is invalid")
    return min(config.maximum_transition_frames, max(config.minimum_transition_frames, value))


def _ceil(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def _frame(seconds: Any, fps: Fraction, rounding: str = "nearest") -> int:
    if isinstance(seconds, bool) or not isinstance(seconds, int | float | Fraction):
        raise ValueError("word time is invalid")
    value = seconds * fps if isinstance(seconds, Fraction) else Fraction(str(seconds)) * fps
    if rounding == "ceil":
        return _ceil(value)
    if rounding == "floor":
        return value.numerator // value.denominator
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def _duration_frames(duration: Any, fps: Fraction) -> int:
    if isinstance(duration, bool) or not isinstance(duration, int | float):
        raise ValueError("catalog duration is invalid")
    value = Fraction(str(duration)) * fps
    return _ceil(value)


def _rejected(
    item_id: str, item_type: str, code: str, reason: str
) -> tuple[dict[str, Any], dict[str, str]]:
    outcome = {
        "item_id": item_id,
        "item_type": item_type,
        "status": "rejected",
        "code": code,
        "reason": reason,
    }
    return outcome, {"id": item_id, "code": code, "reason": reason}


def _licensed(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in {
        "",
        "unlicensed",
        "unknown",
        "none",
        "unspecified",
    }


def _word_maps(words: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[str, int]]:
    rows = words.get("words", [])
    by_id: dict[str, Mapping[str, Any]] = {}
    indexes: dict[str, int] = {}
    if isinstance(rows, list):
        for index, row in enumerate(rows):
            if isinstance(row, Mapping) and isinstance(row.get("id"), str):
                by_id[str(row["id"])] = row
                indexes[str(row["id"])] = index
    return by_id, indexes


def _catalog_map(catalog: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    if catalog is None:
        return result
    for group in ("transitions", "video_fx", "audio_fx", "text_presets", "sfx"):
        entries = catalog.get(group, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, Mapping) and isinstance(entry.get("key"), str):
                result[str(entry["key"])] = entry
    return result


def _continuous_cut(
    cut: Mapping[str, Any],
    words: Mapping[str, Any],
    word_by_id: Mapping[str, Mapping[str, Any]],
    indexes: Mapping[str, int],
    config: CatalogPlacementConfig,
) -> bool:
    remove = cut.get("remove")
    if not isinstance(remove, Mapping):
        return False
    first_index = indexes.get(str(remove.get("from_word")))
    last_index = indexes.get(str(remove.get("to_word")))
    rows = words.get("words", [])
    if first_index is None or last_index is None or not isinstance(rows, list):
        return False
    previous = next((row for row in reversed(rows[:first_index]) if isinstance(row, Mapping)), None)
    following = next((row for row in rows[last_index + 1 :] if isinstance(row, Mapping)), None)
    if not isinstance(previous, Mapping) or not isinstance(following, Mapping):
        return False
    previous_speaker = previous.get("speaker_key")
    following_speaker = following.get("speaker_key")
    try:
        gap_ms = (Fraction(str(following["start"])) - Fraction(str(previous["end"]))) * 1000
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return False
    return (
        isinstance(previous_speaker, str)
        and previous_speaker == following_speaker
        and 0 <= gap_ms <= config.continuous_speech_gap_ms
    )


def _speech_peak(
    frame: int,
    samples: Sequence[int],
    sample_rate: int,
    fps: Fraction,
    config: CatalogPlacementConfig,
) -> bool:
    sample_position = Fraction(frame * sample_rate, 1) / fps
    center = (2 * sample_position.numerator + sample_position.denominator) // (
        2 * sample_position.denominator
    )
    radius = _ceil(Fraction(config.speech_peak_window_ms * sample_rate, 1000))
    start = max(0, center - radius)
    end = min(len(samples), center + radius + 1)
    if start >= end:
        return True
    threshold = 32767 * (10 ** (config.speech_peak_threshold_dbfs / 20))
    return max(abs(samples[index]) for index in range(start, end)) >= threshold


def _path_within(path_value: Any, root: Path) -> Path | None:
    if not isinstance(path_value, str) or not path_value:
        return None
    try:
        path = Path(path_value).resolve(strict=True)
        allowed = root.resolve(strict=True)
        if path.is_file() and path.is_relative_to(allowed):
            return path
    except (OSError, ValueError):
        return None
    return None


def compile_catalog_items(
    edl: Mapping[str, Any],
    words: Mapping[str, Any],
    timeline: Mapping[str, Any],
    catalog: Mapping[str, Any] | None,
    capabilities: Mapping[str, Any] | None,
    *,
    working_root: Path,
    audio_samples: Sequence[int] | None = None,
    sample_rate: int | None = None,
    config: CatalogPlacementConfig | None = None,
) -> CatalogPlacementResult:
    """Resolve transition and SFX intent, emitting only explicitly supported ops."""
    policy = config or CatalogPlacementConfig()
    caps = capabilities or empty_capabilities()
    supported, cap_warnings = supported_operations(caps)
    warnings = [
        {"code": "W_CAPABILITY_UNAVAILABLE", "message": message} for message in cap_warnings
    ]
    sfx_used: list[dict[str, str]] = []
    operations: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    catalog_entries = _catalog_map(catalog)
    word_by_id, indexes = _word_maps(words)
    rows = words.get("words", [])
    fps_text = timeline.get("fps")
    duration_frames = timeline.get("duration_frames")
    if not isinstance(fps_text, str) or type(duration_frames) is not int:
        fps = Fraction(1)
        duration_frames = 0
    else:
        try:
            fps = Fraction(fps_text)
        except (ValueError, ZeroDivisionError):
            fps = Fraction(1)
            duration_frames = 0
    if fps <= 0:
        duration_frames = 0

    def reject(item_id: str, item_type: str, code: str, reason: str) -> None:
        outcome, rejected_item = _rejected(item_id, item_type, code, reason)
        outcomes.append(outcome)
        rejected.append(rejected_item)

    cut_by_id = {
        str(item["id"]): item
        for item in edl.get("cuts", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    transition_counts: dict[int, int] = {}
    transition_rows = edl.get("transitions", [])
    if isinstance(transition_rows, list):
        for index, request in enumerate(transition_rows):
            if not isinstance(request, Mapping):
                continue
            item_id = f"transition-{index}"
            key = request.get("type")
            entry = catalog_entries.get(str(key))
            if entry is None:
                reject(
                    item_id,
                    "transition",
                    "E_CATALOG_MISSING",
                    "transition key is not in the catalog",
                )
                continue
            if entry.get("kind") != "transition":
                reject(item_id, "transition", "E_CATALOG_KIND", "catalog key is not a transition")
                continue
            if entry.get("enabled") is not True:
                reject(item_id, "transition", "E_CATALOG_DISABLED", "transition is disabled")
                continue
            cut_id = request.get("at_cut")
            gap_id = request.get("at_gap")
            rows = words.get("words", [])
            if not isinstance(rows, list):
                rows = []
            if isinstance(cut_id, str) == isinstance(gap_id, str):
                reject(
                    item_id,
                    "transition",
                    "E_TRANSITION_ANCHOR",
                    "transition needs exactly one cut or gap",
                )
                continue
            continuous = False
            if isinstance(cut_id, str):
                cut = cut_by_id.get(cut_id)
                if not isinstance(cut, Mapping):
                    reject(item_id, "transition", "E_REF_CUT", "transition cut ID is missing")
                    continue
                remove = cut.get("remove", {})
                first_word = (
                    word_by_id.get(str(remove.get("from_word")))
                    if isinstance(remove, Mapping)
                    else None
                )
                last_word = (
                    word_by_id.get(str(remove.get("to_word")))
                    if isinstance(remove, Mapping)
                    else None
                )
                if not isinstance(first_word, Mapping) or not isinstance(last_word, Mapping):
                    reject(item_id, "transition", "E_REF_WORD", "transition cut words are missing")
                    continue
                first_index = indexes.get(str(remove.get("from_word")))
                last_index = indexes.get(str(remove.get("to_word")))
                previous_word = (
                    next(
                        (row for row in reversed(rows[:first_index]) if isinstance(row, Mapping)),
                        None,
                    )
                    if first_index is not None
                    else None
                )
                following_word = (
                    next((row for row in rows[last_index + 1 :] if isinstance(row, Mapping)), None)
                    if last_index is not None
                    else None
                )
                if not isinstance(previous_word, Mapping) or not isinstance(
                    following_word, Mapping
                ):
                    reject(
                        item_id,
                        "transition",
                        "E_TRANSITION_CLIP_SHORT",
                        "adjacent clip is unavailable",
                    )
                    continue
                offset = request.get("offset_hint")
                if offset == "before":
                    boundary_time = Fraction(str(first_word["start"]))
                elif offset == "after":
                    boundary_time = Fraction(str(last_word["end"]))
                else:
                    boundary_time = (
                        Fraction(str(first_word["start"])) + Fraction(str(last_word["end"]))
                    ) / 2
                continuous = _continuous_cut(cut, words, word_by_id, indexes, policy)
            else:
                gaps = words.get("gaps", [])
                gap = (
                    next(
                        (
                            row
                            for row in gaps
                            if isinstance(row, Mapping) and row.get("id") == gap_id
                        ),
                        None,
                    )
                    if isinstance(gaps, list)
                    else None
                )
                if gap is None:
                    reject(item_id, "transition", "E_REF_GAP", "transition gap ID is missing")
                    continue
                previous_word = next(
                    (
                        row
                        for row in reversed(rows)
                        if isinstance(row, Mapping)
                        and Fraction(str(row.get("end", 0))) <= Fraction(str(gap["start"]))
                    ),
                    None,
                )
                following_word = next(
                    (
                        row
                        for row in rows
                        if isinstance(row, Mapping)
                        and Fraction(str(row.get("start", 0))) >= Fraction(str(gap["end"]))
                    ),
                    None,
                )
                if not isinstance(previous_word, Mapping) or not isinstance(
                    following_word, Mapping
                ):
                    reject(
                        item_id,
                        "transition",
                        "E_TRANSITION_CLIP_SHORT",
                        "adjacent clip is unavailable",
                    )
                    continue
                offset = request.get("offset_hint")
                if offset == "before":
                    boundary_time = Fraction(str(gap["start"]))
                elif offset == "after":
                    boundary_time = Fraction(str(gap["end"]))
                else:
                    boundary_time = (Fraction(str(gap["start"])) + Fraction(str(gap["end"]))) / 2
            boundary = _frame(boundary_time, fps, "nearest")
            minute_frames = max(1, (60 * fps.numerator) // fps.denominator)
            minute = boundary // minute_frames
            transition_counts[minute] = transition_counts.get(minute, 0) + 1
            if transition_counts[minute] > policy.transitions_per_minute:
                reject(
                    item_id, "transition", "E_TRANSITION_RATE", "transition rate limit is exceeded"
                )
                continue
            required_context = "continuous_speech" if continuous else "topic_boundary"
            allowed_contexts = entry.get("allowed_contexts", [])
            if not isinstance(allowed_contexts, list) or required_context not in allowed_contexts:
                reject(
                    item_id,
                    "transition",
                    "E_TRANSITION_CONTEXT",
                    "transition context is not allowed",
                )
                continue
            tags = set(entry.get("tags", []))
            if (
                continuous
                and "dialogue_safe" not in tags
                and not policy.allow_non_dialogue_safe_continuous
            ):
                reject(
                    item_id,
                    "transition",
                    "E_TRANSITION_NOT_DIALOGUE_SAFE",
                    "transition is not marked dialogue_safe for continuous speech",
                )
                continue
            try:
                duration_frames = resolved_transition_duration(entry, policy)
            except ValueError:
                reject(
                    item_id,
                    "transition",
                    "E_TRANSITION_DURATION",
                    "transition default duration is invalid",
                )
                continue
            if "add_transition" not in supported:
                reject(
                    item_id,
                    "transition",
                    "E_UNSUPPORTED_OP",
                    "executor does not advertise add_transition",
                )
                continue
            # The current timeline contract has source events at frame zero and does not
            # identify post-cut event pairs. Emitting a transition here would guess IDs.
            reject(
                item_id,
                "transition",
                "E_TRANSITION_BOUNDARY_UNRESOLVED",
                "timeline does not identify the adjacent post-cut event pair",
            )

    effect_rows = edl.get("effects", [])
    if isinstance(effect_rows, list):
        event_ids = {
            str(event["id"])
            for event in timeline.get("events", [])
            if isinstance(event, Mapping) and isinstance(event.get("id"), str)
        }
        for index, request in enumerate(effect_rows):
            if not isinstance(request, Mapping):
                continue
            item_id = f"effect-{index}"
            key = str(request.get("key"))
            entry = catalog_entries.get(key)
            if entry is None:
                reject(item_id, "effect", "E_CATALOG_MISSING", "effect key is not in the catalog")
                continue
            if entry.get("kind") not in {"video_fx", "audio_fx"}:
                reject(item_id, "effect", "E_CATALOG_KIND", "catalog key is not an effect")
                continue
            if entry.get("enabled") is not True:
                reject(item_id, "effect", "E_CATALOG_DISABLED", "effect is disabled")
                continue
            if entry.get("params_mode") != "defaults_only":
                reject(
                    item_id,
                    "effect",
                    "E_FX_PARAMETERS_UNPROVEN",
                    "effect parameter support is not proven",
                )
                continue
            target = request.get("at_event")
            if not isinstance(target, str) or target not in event_ids:
                reject(item_id, "effect", "E_REF_EVENT", "effect event ID is missing")
                continue
            if "apply_fx" not in supported:
                reject(
                    item_id, "effect", "E_UNSUPPORTED_OP", "executor does not advertise apply_fx"
                )
                continue
            plugin_id = entry.get("plugin_unique_id")
            if not isinstance(plugin_id, str) or not plugin_id:
                reject(item_id, "effect", "E_CATALOG_ID", "effect identity is unavailable")
                continue
            operations.append(
                {
                    "op": "apply_fx",
                    "target_type": "event",
                    "target_id": target,
                    "catalog_key": key,
                    "plugin_unique_id": plugin_id,
                    "params": {},
                }
            )
            outcomes.append(
                {
                    "item_id": item_id,
                    "item_type": "effect",
                    "status": "applied",
                    "catalog_key": key,
                    "target_event_id": target,
                }
            )

    audio_tracks = sorted(
        (
            row
            for row in timeline.get("tracks", [])
            if isinstance(row, Mapping)
            and row.get("kind") == "audio"
            and isinstance(row.get("id"), str)
        ),
        key=lambda row: int(row.get("index", 0)),
    )
    sfx_rows = edl.get("sfx", [])
    placed: list[tuple[int, int, int]] = []
    per_minute: dict[int, int] = {}
    next_event = (
        max(
            [
                int(str(event.get("id", "e0"))[1:])
                for event in timeline.get("events", [])
                if isinstance(event, Mapping)
                and isinstance(event.get("id"), str)
                and str(event.get("id", "")).startswith("e")
                and str(event.get("id", ""))[1:].isdigit()
            ]
            + [0]
        )
        + 1
    )
    if isinstance(sfx_rows, list):
        for index, request in enumerate(sfx_rows):
            if not isinstance(request, Mapping):
                continue
            item_id = f"sfx-{index}"
            entry = catalog_entries.get(str(request.get("key")))
            if entry is None:
                reject(item_id, "sfx", "E_CATALOG_MISSING", "SFX key is not in the catalog")
                continue
            if entry.get("kind") != "sfx":
                reject(item_id, "sfx", "E_CATALOG_KIND", "catalog key is not an SFX entry")
                continue
            if entry.get("enabled") is not True:
                reject(item_id, "sfx", "E_CATALOG_DISABLED", "SFX entry is disabled")
                continue
            if not _licensed(entry.get("license")):
                reject(item_id, "sfx", "E_SFX_LICENSE", "SFX license metadata is missing")
                continue
            word = word_by_id.get(str(request.get("at_word")))
            if word is None:
                reject(item_id, "sfx", "E_REF_WORD", "SFX word ID is missing")
                continue
            try:
                word_start = _frame(word["start"], fps, "ceil")
                word_end = _frame(word["end"], fps, "ceil")
                offset = request.get("offset_hint")
                proposed = (
                    word_start - 1
                    if offset == "before"
                    else word_end
                    if offset == "after"
                    else _frame(word["start"], fps)
                )
                length = _duration_frames(entry.get("duration"), fps)
            except (KeyError, ValueError, TypeError, ZeroDivisionError):
                reject(item_id, "sfx", "E_SFX_TIMING", "SFX timing metadata is invalid")
                continue
            if length < 1 or proposed < 0 or proposed + length > duration_frames:
                reject(item_id, "sfx", "E_SFX_RANGE", "SFX placement is outside the timeline")
                continue
            if not audio_tracks:
                reject(item_id, "sfx", "E_AUDIO_TRACK", "timeline has no audio track")
                continue
            if "add_audio_event" not in supported:
                reject(
                    item_id,
                    "sfx",
                    "E_UNSUPPORTED_OP",
                    "executor does not advertise add_audio_event",
                )
                continue
            if not isinstance(audio_samples, Sequence) or sample_rate is None or sample_rate < 1:
                reject(
                    item_id,
                    "sfx",
                    "E_SFX_AUDIO_UNAVAILABLE",
                    "speech peak analysis audio is unavailable",
                )
                continue
            candidates = [proposed]
            for shift in range(1, max(0, policy.placement_search_window_frames) + 1):
                candidates.extend((proposed - shift, proposed + shift))
            selected: int | None = None
            for candidate in candidates:
                if candidate < 0 or candidate + length > duration_frames:
                    continue
                if policy.avoid_speech_peaks and _speech_peak(
                    candidate, audio_samples, sample_rate, fps, policy
                ):
                    continue
                if not policy.allow_sfx_overlap and any(
                    candidate < old_end and candidate + length > old_start
                    for old_start, old_end, _ in placed
                ):
                    continue
                selected = candidate
                break
            if selected is None:
                reject(
                    item_id,
                    "sfx",
                    "E_SFX_NO_SAFE_WINDOW",
                    "no safe non-overlapping SFX window was found",
                )
                continue
            minute_frames = max(1, (60 * fps.numerator) // fps.denominator)
            minute = selected // minute_frames
            if per_minute.get(minute, 0) >= policy.sfx_per_minute:
                reject(item_id, "sfx", "E_SFX_RATE", "SFX rate limit is exceeded")
                continue
            path = _path_within(entry.get("path"), working_root)
            if path is None:
                reject(
                    item_id, "sfx", "E_ASSET_PATH", "SFX asset is outside the job working directory"
                )
                continue
            if "loudness_lufs" not in entry or "peak_dbfs" not in entry:
                reject(
                    item_id,
                    "sfx",
                    "E_SFX_MEASUREMENT",
                    "SFX loudness and peak measurements are required",
                )
                continue
            try:
                loudness = float(entry["loudness_lufs"])
                peak = float(entry["peak_dbfs"])
                hint = 0.0
                if not all(math.isfinite(value) for value in (loudness, peak, hint)):
                    raise ValueError
            except (TypeError, ValueError):
                reject(
                    item_id,
                    "sfx",
                    "E_SFX_MEASUREMENT",
                    "SFX loudness and peak measurements are invalid",
                )
                continue
            wanted_gain = policy.target_sfx_loudness_lufs - loudness + hint
            gain = min(
                wanted_gain,
                policy.maximum_sfx_gain_db,
                policy.maximum_sfx_peak_dbfs - peak,
            )
            if gain < policy.minimum_sfx_gain_db:
                reject(
                    item_id, "sfx", "E_SFX_GAIN", "safe gain would be below the configured floor"
                )
                continue
            operation = {
                "op": "add_audio_event",
                "event_id": f"e{next_event}",
                "track_id": str(audio_tracks[0]["id"]),
                "catalog_key": str(request["key"]),
                "file_path": str(path),
                "start_frame": selected,
                "length_frames": length,
                "gain_db": round(gain, 4),
            }
            operations.append(operation)
            sfx_used.append({"key": str(request["key"]), "license": str(entry["license"])})
            placed.append((selected, selected + length, index))
            per_minute[minute] = per_minute.get(minute, 0) + 1
            next_event += 1
            delta = selected - proposed
            gain_delta = gain - wanted_gain
            adjusted = delta != 0 or gain_delta < -0.0001
            outcomes.append(
                {
                    "item_id": item_id,
                    "item_type": "sfx",
                    "status": "adjusted" if adjusted else "applied",
                    "catalog_key": str(request["key"]),
                    "start_frame": selected,
                    "duration_frames": length,
                    "gain_db": round(gain, 4),
                    **(
                        {
                            "reason": (
                                "placement moved away from a speech peak or gain was reduced "
                                "to the configured ceiling"
                            ),
                            **({"delta_frames": abs(delta)} if delta else {}),
                            **(
                                {"adjustment_db": round(gain_delta, 4)}
                                if gain_delta < -0.0001
                                else {}
                            ),
                        }
                        if adjusted
                        else {}
                    ),
                }
            )
    return CatalogPlacementResult(operations, outcomes, rejected, warnings, sfx_used)
