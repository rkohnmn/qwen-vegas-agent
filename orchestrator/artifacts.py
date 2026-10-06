"""Human-review artifacts derived only from validated words and compiled frame ops."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .compiler import FrameInterval, kept_intervals


def _timecode(frame: int, fps: str) -> str:
    from fractions import Fraction

    rate = Fraction(fps)
    nominal = max(1, (rate.numerator * 2 + rate.denominator) // (2 * rate.denominator))
    total_seconds, frame_number = divmod(frame, nominal)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_number:02d}"


def write_json(path: Path, document: Any) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markers(
    path: Path,
    operations: list[dict[str, Any]],
    fps: str,
    *,
    decisions: list[dict[str, Any]] | None = None,
) -> None:
    metadata = {item["id"]: item for item in decisions or [] if isinstance(item.get("id"), str)}
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("frame", "timecode", "label", "category", "confidence"))
        for operation in operations:
            if operation.get("op") != "add_marker":
                continue
            frame = operation["frame"]
            label = operation["label"]
            parts = label.split("_")
            identifier = parts[2] if len(parts) >= 5 and parts[:2] == ["M1", "CUT"] else ""
            item = metadata.get(identifier, {})
            category = item.get("category")
            if not isinstance(category, str):
                category = "_".join(parts[3:-1]) if identifier else "other"
            confidence = item.get("confidence", 0.0)
            writer.writerow((frame, _timecode(frame, fps), label, category, f"{confidence:.2f}"))


def write_cmx_edl(path: Path, fps: str, duration_frames: int, removed: list[FrameInterval]) -> None:
    preserved = kept_intervals(duration_frames, removed)
    lines = ["TITLE: M1 OFFLINE ROUGH CUT", "FCM: NON-DROP FRAME", ""]
    record = 0
    for index, (source_in, source_out) in enumerate(preserved, start=1):
        length = source_out - source_in
        if length <= 0:
            continue
        record_out = record + length
        lines.append(
            f"{index:03d}  AX       V     C        "
            f"{_timecode(source_in, fps)} {_timecode(source_out, fps)} "
            f"{_timecode(record, fps)} {_timecode(record_out, fps)}"
        )
        record = record_out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_review(
    path: Path, edl: dict[str, Any], words: dict[str, Any], report: dict[str, Any]
) -> None:
    rows = words.get("words", [])
    indices = {row.get("id"): i for i, row in enumerate(rows) if isinstance(row, dict)}
    lines = [
        "# Rough cut review",
        "",
        edl.get("summary", ""),
        "",
        "## Summary",
        "",
        "| Cut count | Total removed frames | Removed percent |",
        "|---:|---:|---:|",
        f"| {len([*edl.get('cuts', []), *edl.get('gap_actions', [])])} "
        f"| {report['removed_frames']} | {report['removed_percent']:.2f}% |",
        "",
        "## Planned cuts",
        "",
    ]
    decisions = [*edl.get("cuts", []), *edl.get("gap_actions", [])]
    if not decisions:
        lines.append("No cuts were selected.")
    for item in decisions:
        identifier = item.get("id", "unknown")
        reason = item.get("reason", "")
        lines.extend(
            [
                f"### {identifier}",
                "",
                f"- Category: {item.get('category', 'silence')}",
                f"- Confidence: {item.get('confidence', 0):.2f}",
                f"- Reason: {reason}",
            ]
        )
        remove = item.get("remove", {})
        if isinstance(remove, dict):
            first = indices.get(remove.get("from_word"))
            last = indices.get(remove.get("to_word"))
            if first is not None and last is not None:
                context = rows[max(0, first - 8) : min(len(rows), last + 9)]
                excerpt = " ".join(str(row.get("text", "")) for row in context)
                lines.append(f"- Transcript context: {excerpt}")
        gap_id = item.get("gap_id")
        if gap_id:
            lines.append(f"- Gap: {gap_id}")
        lines.append("")
    lines.extend(
        [
            "## Compiler report",
            "",
            f"- Removed: {report['removed_frames']} / {report['source_frames']} frames "
            f"({report['removed_percent']:.2f}%)",
            f"- Warnings: {len(report['warnings'])}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
