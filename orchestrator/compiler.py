"""Deterministic rational-frame compiler for M1 cuts and measured silence."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any


@dataclass(frozen=True, slots=True)
class CompileConfig:
    head_pad_ms: int = 40
    tail_pad_ms: int = 80
    min_gap_after_cut_ms: int = 120
    audio_crossfade_ms: int = 20
    max_removed_percent: float = 35.0
    snap_zero_crossing: bool = False
    zero_crossing_window_ms: int = 20


@dataclass(frozen=True, slots=True)
class FrameInterval:
    start: int
    end: int
    cut_ids: tuple[str, ...]
    category: str


def _as_fraction(value: int | float | Fraction) -> Fraction:
    if isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError("time value must be finite")
    return value if isinstance(value, Fraction) else Fraction(str(value))


def floor_fraction(value: Fraction) -> int:
    return value.numerator // value.denominator


def ceil_fraction(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def time_to_frame(
    seconds: int | float | Fraction, fps: Fraction, *, rounding: str = "nearest"
) -> int:
    """Convert a decimal time to an integer frame using exact rational arithmetic."""
    value = _as_fraction(seconds) * fps
    if rounding == "floor":
        return floor_fraction(value)
    if rounding == "ceil":
        return ceil_fraction(value)
    if rounding != "nearest":
        raise ValueError("rounding must be floor, ceil, or nearest")
    return floor_fraction(value + Fraction(1, 2))


def frame_to_time(frame: int, fps: Fraction) -> Fraction:
    if frame < 0 or fps <= 0:
        raise ValueError("frame and fps must be non-negative and positive")
    return Fraction(frame, 1) / fps


def _snap_to_zero_crossing(
    target_frame: int,
    minimum_frame: int,
    maximum_frame: int,
    samples: Sequence[int] | None,
    sample_rate: int | None,
    fps: Fraction,
    window_ms: int,
) -> tuple[int, bool]:
    """Prefer a nearby PCM sign change while keeping the boundary on a safe frame."""
    if samples is None or sample_rate is None or sample_rate < 1 or len(samples) < 2:
        return target_frame, False
    center_sample = floor_fraction(Fraction(target_frame * sample_rate, 1) / fps + Fraction(1, 2))
    radius = ceil_fraction(Fraction(window_ms * sample_rate, 1000))
    first = max(1, center_sample - radius)
    last = min(len(samples) - 1, center_sample + radius)
    target_time = Fraction(target_frame, 1) / fps
    candidates: list[tuple[Fraction, int]] = []
    for sample_index in range(first, last + 1):
        before, after = samples[sample_index - 1], samples[sample_index]
        if before == 0 or after == 0 or (before < 0 < after) or (after < 0 < before):
            frame = time_to_frame(Fraction(sample_index, sample_rate), fps)
            if minimum_frame <= frame <= maximum_frame:
                distance = abs(Fraction(sample_index, sample_rate) - target_time)
                candidates.append((distance, frame))
    if not candidates:
        return target_frame, False
    return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[1], True


def _intervals(items: list[FrameInterval]) -> list[FrameInterval]:
    ordered = sorted(items, key=lambda interval: (interval.start, interval.end))
    merged: list[FrameInterval] = []
    for item in ordered:
        if not merged or item.start > merged[-1].end:
            merged.append(item)
            continue
        previous = merged[-1]
        merged[-1] = FrameInterval(
            previous.start,
            max(previous.end, item.end),
            tuple(dict.fromkeys((*previous.cut_ids, *item.cut_ids))),
            previous.category if previous.category == item.category else "mixed",
        )
    return merged


def compile_edl(
    edl: dict[str, Any],
    words: dict[str, Any],
    timeline: dict[str, Any],
    *,
    job_id: str,
    working_copy_path: str,
    config: CompileConfig | None = None,
    audio_samples: Sequence[int] | None = None,
    sample_rate: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[FrameInterval]]:
    """Resolve planner IDs to frame ranges and marker operations; never mutate media."""
    limits = config or CompileConfig()
    fps_text = timeline.get("fps")
    if not isinstance(fps_text, str):
        raise ValueError("timeline frame rate is missing")
    fps = Fraction(fps_text)
    duration_frames = timeline.get("duration_frames")
    if type(duration_frames) is not int or duration_frames < 1:
        raise ValueError("timeline duration is invalid")
    rows = words.get("words", [])
    if not isinstance(rows, list):
        raise ValueError("words document is invalid")
    word_by_id: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            word_by_id[row["id"]] = (index, row)
    aligned = [
        (index, row)
        for index, row in enumerate(rows)
        if isinstance(row, dict) and row.get("alignment_status", "aligned") == "aligned"
    ]
    candidates: list[FrameInterval] = []
    snaps: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    item_outcomes: list[dict[str, Any]] = []

    def reject_item(item_id: str, item_type: str, code: str, reason: str) -> None:
        rejected.append({"id": item_id, "code": code, "reason": reason})
        item_outcomes.append(
            {
                "item_id": item_id,
                "item_type": item_type,
                "status": "rejected",
                "code": code,
                "reason": reason,
            }
        )

    padding_start = Fraction(limits.head_pad_ms, 1000)
    padding_end = Fraction(limits.tail_pad_ms, 1000)
    for cut in edl.get("cuts", []):
        cut_id = cut.get("id", "unknown") if isinstance(cut, dict) else "unknown"
        remove = cut.get("remove", {}) if isinstance(cut, dict) else {}
        from_word = remove.get("from_word") if isinstance(remove, dict) else None
        to_word = remove.get("to_word") if isinstance(remove, dict) else None
        first = word_by_id.get(from_word) if isinstance(from_word, str) else None
        last = word_by_id.get(to_word) if isinstance(to_word, str) else None
        if first is None or last is None:
            reject_item(str(cut_id), "cut", "E_REF_WORD", "cut word ID is missing")
            continue
        first_index, first_word = first
        last_index, last_word = last
        if (
            first_word.get("alignment_status", "aligned") != "aligned"
            or last_word.get("alignment_status", "aligned") != "aligned"
        ):
            reject_item(str(cut_id), "cut", "E_WORD_UNALIGNED", "cut word has no aligned time")
            continue
        if first_index > last_index:
            reject_item(str(cut_id), "cut", "E_CUT_ORDER", "cut word range is reversed")
            continue
        if any(
            isinstance(row, dict) and row.get("alignment_status", "aligned") != "aligned"
            for row in rows[first_index : last_index + 1]
        ):
            reject_item(
                str(cut_id),
                "cut",
                "E_WORD_UNALIGNED",
                "cut range includes a word without aligned timing",
            )
            continue
        start_sec = _as_fraction(first_word["start"]) - padding_start
        end_sec = _as_fraction(last_word["end"]) + padding_end
        start_frame = max(0, floor_fraction(start_sec * fps))
        end_frame = min(duration_frames, ceil_fraction(end_sec * fps))
        previous = next((row for index, row in reversed(aligned) if index < first_index), None)
        following = next((row for index, row in aligned if index > last_index), None)
        previous_end = (
            ceil_fraction(_as_fraction(previous["end"]) * fps) if previous is not None else 0
        )
        following_start = (
            floor_fraction(_as_fraction(following["start"]) * fps)
            if following is not None
            else duration_frames
        )
        start_frame = max(start_frame, previous_end)
        end_frame = min(end_frame, following_start)
        proposed_start_frame, proposed_end_frame = start_frame, end_frame
        start_frame, start_zero_crossing = _snap_to_zero_crossing(
            start_frame,
            previous_end,
            floor_fraction(_as_fraction(first_word["start"]) * fps),
            audio_samples if limits.snap_zero_crossing else None,
            sample_rate,
            fps,
            limits.zero_crossing_window_ms,
        )
        end_frame, end_zero_crossing = _snap_to_zero_crossing(
            end_frame,
            ceil_fraction(_as_fraction(last_word["end"]) * fps),
            following_start,
            audio_samples if limits.snap_zero_crossing else None,
            sample_rate,
            fps,
            limits.zero_crossing_window_ms,
        )
        if end_frame <= start_frame:
            reject_item(str(cut_id), "cut", "E_EMPTY_RANGE", "snapping leaves no safe cut frames")
            continue
        if previous is not None and following is not None:
            preserved_gap = (start_frame - previous_end) + (following_start - end_frame)
            minimum_gap = ceil_fraction(Fraction(limits.min_gap_after_cut_ms, 1000) * fps)
            if preserved_gap < minimum_gap:
                reject_item(
                    str(cut_id),
                    "cut",
                    "E_PACING_GAP",
                    "cut would leave less than the configured inter-word gap",
                )
                continue
        delta_frames = abs(start_frame - proposed_start_frame) + abs(end_frame - proposed_end_frame)
        item_outcomes.append(
            {
                "item_id": str(cut_id),
                "item_type": "cut",
                "status": "adjusted" if delta_frames else "applied",
                **(
                    {
                        "reason": "one or both boundaries moved to a nearby zero crossing",
                        "delta_frames": delta_frames,
                    }
                    if delta_frames
                    else {}
                ),
            }
        )
        candidates.append(
            FrameInterval(start_frame, end_frame, (str(cut_id),), str(cut.get("category", "other")))
        )
        for boundary, frame, word_time, zero_crossing in (
            ("in", start_frame, float(first_word["start"]), start_zero_crossing),
            ("out", end_frame, float(last_word["end"]), end_zero_crossing),
        ):
            final_time = frame_to_time(frame, fps)
            snaps.append(
                {
                    "id": f"{cut_id}_{boundary}",
                    "word_time": word_time,
                    "final_time": f"{final_time.numerator}/{final_time.denominator}",
                    "final_time_frame": frame,
                    "delta_ms": round(float(final_time - _as_fraction(word_time)) * 1000, 4),
                    "reason": (
                        f"word {boundary} padding and safe frame grid; "
                        + (
                            "nearest zero crossing"
                            if zero_crossing
                            else "zero crossing unavailable"
                        )
                    ),
                }
            )

    gaps = {gap.get("id"): gap for gap in words.get("gaps", []) if isinstance(gap, dict)}
    for action in edl.get("gap_actions", []):
        action_id = action.get("id", "unknown") if isinstance(action, dict) else "unknown"
        gap = gaps.get(action.get("gap_id")) if isinstance(action, dict) else None
        if gap is None:
            reject_item(str(action_id), "gap_action", "E_REF_GAP", "gap ID is missing")
            continue
        start_frame = max(0, ceil_fraction(_as_fraction(gap["start"]) * fps))
        end_frame = min(duration_frames, floor_fraction(_as_fraction(gap["end"]) * fps))
        refinement = gap.get("refinement", {})
        asr_start = (
            refinement.get("asr_start", gap["start"])
            if isinstance(refinement, dict)
            else gap["start"]
        )
        asr_end = (
            refinement.get("asr_end", gap["end"]) if isinstance(refinement, dict) else gap["end"]
        )
        if not isinstance(asr_start, int | float) or isinstance(asr_start, bool):
            asr_start = gap["start"]
        if not isinstance(asr_end, int | float) or isinstance(asr_end, bool):
            asr_end = gap["end"]
        previous = next(
            (
                row
                for _index, row in reversed(aligned)
                if _as_fraction(row["end"]) <= _as_fraction(asr_start) + Fraction(1, 1000000)
            ),
            None,
        )
        following = next(
            (
                row
                for _index, row in aligned
                if _as_fraction(row["start"]) >= _as_fraction(asr_end) - Fraction(1, 1000000)
            ),
            None,
        )
        if previous is not None:
            start_frame = max(start_frame, ceil_fraction(_as_fraction(previous["end"]) * fps))
        if following is not None:
            end_frame = min(end_frame, floor_fraction(_as_fraction(following["start"]) * fps))
        if end_frame <= start_frame:
            reject_item(
                str(action_id), "gap_action", "E_EMPTY_RANGE", "gap has no safe frame range"
            )
            continue
        proposed_ranges: list[tuple[int, int]]
        if action.get("mode") == "shorten":
            retain = ceil_fraction(Fraction(limits.min_gap_after_cut_ms, 1000) * fps)
            available = end_frame - start_frame
            if available <= retain:
                reject_item(
                    str(action_id),
                    "gap_action",
                    "E_EMPTY_RANGE",
                    "gap is already at or below the configured retained length",
                )
                continue
            keep_start = start_frame + (available - retain) // 2
            keep_end = keep_start + retain
            proposed_ranges = []
            if keep_start > start_frame:
                proposed_ranges.append((start_frame, keep_start))
            if keep_end < end_frame:
                proposed_ranges.append((keep_end, end_frame))
        else:
            proposed_ranges = [(start_frame, end_frame)]

        delta_frames = 0
        for range_index, (range_start, range_end) in enumerate(proposed_ranges, start=1):
            snapped_start, start_zero_crossing = _snap_to_zero_crossing(
                range_start,
                range_start,
                range_end,
                audio_samples if limits.snap_zero_crossing else None,
                sample_rate,
                fps,
                limits.zero_crossing_window_ms,
            )
            snapped_end, end_zero_crossing = _snap_to_zero_crossing(
                range_end,
                range_start,
                range_end,
                audio_samples if limits.snap_zero_crossing else None,
                sample_rate,
                fps,
                limits.zero_crossing_window_ms,
            )
            if snapped_end <= snapped_start:
                snapped_start, snapped_end = range_start, range_end
                start_zero_crossing = end_zero_crossing = False
            delta_frames += abs(snapped_start - range_start) + abs(snapped_end - range_end)
            candidates.append(
                FrameInterval(snapped_start, snapped_end, (str(action_id),), "silence")
            )
            for boundary, frame, original_frame, zero_crossing in (
                ("in", snapped_start, range_start, start_zero_crossing),
                ("out", snapped_end, range_end, end_zero_crossing),
            ):
                original_time = frame_to_time(original_frame, fps)
                final_time = frame_to_time(frame, fps)
                snaps.append(
                    {
                        "id": f"{action_id}_j{range_index}_{boundary}",
                        "word_time": float(original_time),
                        "final_time": f"{final_time.numerator}/{final_time.denominator}",
                        "final_time_frame": frame,
                        "delta_ms": round(float(final_time - original_time) * 1000, 4),
                        "reason": (
                            "inward measured-silence frame snap; "
                            + (
                                "nearest zero crossing"
                                if zero_crossing
                                else "zero crossing unavailable"
                            )
                        ),
                    }
                )

        item_outcomes.append(
            {
                "item_id": str(action_id),
                "item_type": "gap_action",
                "status": "adjusted" if delta_frames else "applied",
                **(
                    {
                        "reason": "one or more silence boundaries moved to nearby zero crossings",
                        "delta_frames": delta_frames,
                    }
                    if delta_frames
                    else {}
                ),
            }
        )

    intervals = _intervals(candidates)
    removed_frames = sum(item.end - item.start for item in intervals)
    removed_percent = round(removed_frames * 100 / duration_frames, 6)
    warnings: list[dict[str, str]] = []
    if removed_percent > limits.max_removed_percent:
        warnings.append(
            {
                "code": "W_REMOVED_PERCENT",
                "message": "planned removal exceeds configured review threshold",
            }
        )

    tracks = timeline.get("tracks", [])
    track_ids = [
        track["id"]
        for track in tracks
        if isinstance(track, dict) and isinstance(track.get("id"), str)
    ]
    group_ids = [
        group["id"]
        for group in timeline.get("groups", [])
        if isinstance(group, dict) and isinstance(group.get("id"), str)
    ]
    source_hash = timeline.get("source_hash", "")
    bare_hash = source_hash.removeprefix("sha256:") if isinstance(source_hash, str) else ""
    if not track_ids or not group_ids or len(bare_hash) != 64:
        raise ValueError("timeline is missing linked-track identity")
    operations: list[dict[str, Any]] = []
    marker_index = 1
    category_by_id = {
        item.get("id"): item.get("category", "silence")
        for item in [*edl.get("cuts", []), *edl.get("gap_actions", [])]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for interval in intervals:
        for cut_id in interval.cut_ids:
            category = category_by_id.get(cut_id, interval.category)
            for frame, suffix in ((interval.start, "IN"), (interval.end, "OUT")):
                operations.append(
                    {
                        "op": "add_marker",
                        "marker_id": f"m{marker_index}",
                        "frame": frame,
                        "label": f"M1_CUT_{cut_id}_{category}_{suffix}",
                    }
                )
                marker_index += 1
        operations.append(
            {
                "op": "delete_range",
                "start_frame": interval.start,
                "end_frame": interval.end,
                "track_ids": track_ids,
                "group_ids": group_ids,
                "item_ids": list(interval.cut_ids),
            }
        )

    fade_frames = max(0, time_to_frame(limits.audio_crossfade_ms / 1000, fps, rounding="nearest"))
    fade_decisions: list[dict[str, Any]] = []
    cursor = 0
    for interval_index, interval in enumerate(intervals, start=1):
        has_left = interval.start > cursor
        has_right = interval.end < duration_frames
        decision = (
            "crossfade"
            if has_left and has_right and fade_frames > 0
            else "fade_out_in"
            if has_left or has_right
            else "none"
        )
        for cut_id in interval.cut_ids:
            fade_decisions.append(
                {
                    "id": f"{cut_id}_j{interval_index}",
                    "decision": decision,
                    "frames": fade_frames if decision != "none" else 0,
                    "reason": (
                        "M1 per-cut audio join policy; rendered joins are measured separately"
                    ),
                }
            )
        cursor = interval.end

    ops = {
        "schema_version": "1.1.0",
        "header": {
            "job_id": job_id,
            "working_copy_path": working_copy_path,
            "fps": fps_text,
            "source_hashes": [{"source_id": "source_0", "sha256": bare_hash}],
        },
        "operations": operations,
    }
    report = {
        "schema_version": "2.0.0",
        "source_frames": duration_frames,
        "removed_frames": removed_frames,
        "removed_percent": removed_percent,
        "warnings": warnings,
        "rejected_items": rejected,
        "item_outcomes": item_outcomes,
        "snaps": snaps,
        "fade_decisions": fade_decisions,
    }
    return ops, report, intervals


def kept_intervals(duration_frames: int, removed: list[FrameInterval]) -> list[tuple[int, int]]:
    """Return half-open source frame ranges preserved by the edit."""
    kept: list[tuple[int, int]] = []
    cursor = 0
    for interval in removed:
        if interval.start > cursor:
            kept.append((cursor, interval.start))
        cursor = max(cursor, interval.end)
    if cursor < duration_frames:
        kept.append((cursor, duration_frames))
    return kept
