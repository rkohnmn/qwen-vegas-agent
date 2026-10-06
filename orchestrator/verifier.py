"""Audio join and cut-boundary verification for reference renders."""

from __future__ import annotations

import math
import wave
from array import array
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

from .compiler import FrameInterval, ceil_fraction, floor_fraction


def _pcm(path: str | Path) -> tuple[int, array[int]]:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("verification requires mono PCM16 audio")
        values = array("h")
        values.frombytes(source.readframes(source.getnframes()))
        return source.getframerate(), values


def _rms(values: Sequence[int]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(value * value for value in values) / len(values)) / 32768.0


def verify_audio(
    audio_path: str | Path,
    join_samples: Sequence[int],
    *,
    removed_percent: float = 0.0,
    max_removed_percent: float = 35.0,
    max_click_delta: float = 0.12,
    max_level_step_db: float = 8.0,
    words: dict[str, Any] | None = None,
    fps: str | None = None,
    removed: Sequence[FrameInterval] = (),
    min_interword_gap_ms: int = 120,
    max_interword_gap_ms: int = 1800,
) -> dict[str, Any]:
    """Report discontinuity and pre/post RMS level steps for every rendered join."""
    sample_rate, samples = _pcm(audio_path)
    checks: list[dict[str, Any]] = []
    fixes: list[dict[str, Any]] = []
    radius = max(1, sample_rate // 20)
    for index, point in enumerate(join_samples, start=1):
        join_id = f"join_{index}"
        if point <= 0 or point >= len(samples):
            click = 1.0
            level_step = 999.0
        else:
            click = abs(samples[point] - samples[point - 1]) / 32768.0
            before = _rms(samples[max(0, point - radius) : point])
            after = _rms(samples[point : min(len(samples), point + radius)])
            level_step = abs(20 * math.log10(max(after, 1e-6) / max(before, 1e-6)))
        click_ok = click <= max_click_delta
        level_ok = level_step <= max_level_step_db
        checks.extend(
            [
                {
                    "id": f"{join_id}_click",
                    "name": "click_discontinuity",
                    "scope": "join",
                    "target_id": join_id,
                    "passed": click_ok,
                    "threshold": max_click_delta,
                    "measured": round(click, 6),
                    "unit": "full_scale_delta",
                },
                {
                    "id": f"{join_id}_level",
                    "name": "level_step",
                    "scope": "join",
                    "target_id": join_id,
                    "passed": level_ok,
                    "threshold": max_level_step_db,
                    "measured": round(level_step, 4),
                    "unit": "dB",
                },
            ]
        )
        if not click_ok or not level_ok:
            fixes.append(
                {
                    "id": f"fix_{join_id}",
                    "target_id": join_id,
                    "code": "widen_crossfade",
                    "suggested_value_ms": 40.0,
                    "message": "Review this audio join and widen the crossfade if needed.",
                }
            )
    if words is not None and fps is not None:
        rate = Fraction(fps)
        aligned_rows = [
            row
            for row in words.get("words", [])
            if isinstance(row, dict)
            and row.get("alignment_status", "aligned") == "aligned"
            and isinstance(row.get("start"), int | float)
            and isinstance(row.get("end"), int | float)
        ]
        frame_rows = []
        for row in aligned_rows:
            frame_rows.append(
                {
                    "id": row.get("id", "unknown"),
                    "track": row.get("track", "audio_0"),
                    "start": floor_fraction(Fraction(str(row["start"])) * rate),
                    "end": ceil_fraction(Fraction(str(row["end"])) * rate),
                }
            )

        for interval in removed:
            for cut_id in interval.cut_ids:
                for boundary, suffix in ((interval.start, "in"), (interval.end, "out")):
                    clipped = any(row["start"] < boundary < row["end"] for row in frame_rows)
                    check_id = f"{cut_id}_{suffix}"
                    checks.append(
                        {
                            "id": check_id,
                            "name": "clipped_word",
                            "scope": "cut",
                            "target_id": cut_id,
                            "passed": not clipped,
                            "threshold": 0,
                            "measured": 1 if clipped else 0,
                            "unit": "boundary_inside_word",
                        }
                    )
                    if clipped:
                        fixes.append(
                            {
                                "id": f"fix_{check_id}",
                                "target_id": cut_id,
                                "code": "review_word_alignment",
                                "message": (
                                    "Review this cut boundary against the aligned word span."
                                ),
                            }
                        )

        def map_frame(frame: int) -> int:
            removed_before = sum(
                interval.end - interval.start for interval in removed if interval.end <= frame
            )
            return frame - removed_before

        by_track: dict[str, list[dict[str, Any]]] = {}
        for row in frame_rows:
            intersects = [
                interval
                for interval in removed
                if interval.start < row["end"] and interval.end > row["start"]
            ]
            if intersects:
                continue
            by_track.setdefault(str(row["track"]), []).append(row)

        for track_rows in by_track.values():
            track_rows.sort(key=lambda row: (row["start"], row["end"]))
            for previous, following in zip(track_rows, track_rows[1:], strict=False):
                between = any(
                    interval.start >= previous["end"] and interval.end <= following["start"]
                    for interval in removed
                )
                if not between:
                    continue
                gap_frames = map_frame(following["start"]) - map_frame(previous["end"])
                gap_ms = float(Fraction(gap_frames * 1000, 1) / rate)
                minimum_ok = gap_ms >= min_interword_gap_ms
                maximum_ok = gap_ms <= max_interword_gap_ms
                pair_id = f"{previous['id']}_{following['id']}"
                for suffix, passed, threshold in (
                    ("min", minimum_ok, min_interword_gap_ms),
                    ("max", maximum_ok, max_interword_gap_ms),
                ):
                    checks.append(
                        {
                            "id": f"pacing_{suffix}_{pair_id}",
                            "name": "pacing",
                            "scope": "cut",
                            "target_id": str(following["id"]),
                            "passed": passed,
                            "threshold": threshold,
                            "measured": round(gap_ms, 3),
                            "unit": "ms",
                        }
                    )
                if not minimum_ok or not maximum_ok:
                    fixes.append(
                        {
                            "id": f"fix_pacing_{pair_id}",
                            "target_id": str(following["id"]),
                            "code": "move_cut_to_silence",
                            "suggested_value_ms": float(min_interword_gap_ms),
                            "message": (
                                "Review the inter-word gap and move any nearby cut into silence."
                            ),
                        }
                    )

    removed_ok = removed_percent <= max_removed_percent
    checks.append(
        {
            "id": "removed_percent",
            "name": "removed_percent",
            "scope": "run",
            "passed": removed_ok,
            "threshold": max_removed_percent,
            "measured": round(removed_percent, 4),
            "unit": "percent",
        }
    )
    if not removed_ok:
        fixes.append(
            {
                "id": "fix_removed_percent",
                "target_id": "run",
                "code": "reduce_removed_percent",
                "message": "Review the planned amount of removed footage.",
            }
        )
    return {
        "schema_version": "1.0.0",
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "fix_suggestions": fixes,
    }
