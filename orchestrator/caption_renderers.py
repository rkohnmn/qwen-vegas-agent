from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol

from orchestrator.captions import CaptionConfig, resolve_speaker_color
from orchestrator.childenv import safe_child_environment
from orchestrator.compiler import time_to_frame

_TIMESTAMP_RE = re.compile(r"^(\d+):(\d{2}):(\d{2})[,.](\d{2,3})$")


class CaptionRenderError(RuntimeError):
    """Expected failure while exporting or burning caption sidecars."""


class CaptionRenderUnavailable(CaptionRenderError):
    """The selected renderer depends on a missing or unverified runtime."""


class CaptionRenderer(Protocol):
    """Offline renderer interface for frame-resolved captions."""

    def write_sidecars(
        self,
        output_dir: str | Path,
        document: Mapping[str, Any],
        report: Mapping[str, Any],
        speakers_document: Mapping[str, Any],
        config: CaptionConfig,
    ) -> tuple[Path, Path, Path, Path]: ...


def write_caption_review(
    path: str | Path, report: Mapping[str, Any], *, heading: str = "Caption review"
) -> None:
    """Append a transcript-free caption summary for human review."""
    warnings = report.get("warnings", [])
    low_confidence = report.get("low_confidence", [])
    lines = [
        f"\n## {heading}\n\n",
        f"Generated captions: {report.get('caption_count', 0)}\n\n",
        f"Warnings: {len(warnings) if isinstance(warnings, list) else 0}\n\n",
    ]
    if isinstance(warnings, list) and warnings:
        lines.extend(["| Code | Caption | Speaker | Frames | Detail |\n|---|---|---|---|---|\n"])
        for item in warnings:
            if not isinstance(item, Mapping):
                continue
            caption_id = item.get("caption_id", "")
            speaker_key = item.get("speaker_key", "")
            start_frame = item.get("start_frame", "")
            end_frame = item.get("end_frame", "")
            frames = f"{start_frame}–{end_frame}" if start_frame != "" else ""
            detail = item.get("contrast_ratio", "")
            code = item.get("code", "W_UNKNOWN")
            lines.append(f"| {code} | {caption_id} | {speaker_key} | {frames} | {detail} |\n")
        lines.append("\n")
    if isinstance(low_confidence, list) and low_confidence:
        lines.extend(
            [
                "Low-confidence captions: " + str(len(low_confidence)) + "\n\n",
                "| Caption | Speaker | Frames | Reasons | Source words |\n|---|---|---|---|---|\n",
            ]
        )
        for item in low_confidence:
            if not isinstance(item, Mapping):
                continue
            lines.append(
                "| {caption} | {speaker} | {start}–{end} | {reasons} | {words} |\n".format(
                    caption=item.get("caption_id", ""),
                    speaker=item.get("speaker_key", ""),
                    start=item.get("start_frame", ""),
                    end=item.get("end_frame", ""),
                    reasons=", ".join(str(value) for value in item.get("reasons", [])),
                    words=", ".join(str(value) for value in item.get("source_word_ids", [])),
                )
            )
        lines.append("\n")
    with Path(path).open("a", encoding="utf-8") as output:
        output.writelines(lines)


def _frame_milliseconds(frame: int, fps: Fraction) -> int:
    value = Fraction(frame * 1000, 1) / fps
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def _frame_centiseconds(frame: int, fps: Fraction) -> int:
    value = Fraction(frame * 100, 1) / fps
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def _format_timestamp(value: int, separator: str) -> str:
    if separator == ".":
        hours, remainder = divmod(max(0, value), 360_000)
        minutes, remainder = divmod(remainder, 6_000)
        seconds, fraction = divmod(remainder, 100)
        return f"{hours}:{minutes:02}:{seconds:02}.{fraction:02}"
    hours, remainder = divmod(max(0, value), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, fraction = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{fraction:03}"


def _parse_timestamp(value: str, *, centiseconds: bool) -> Fraction:
    match = _TIMESTAMP_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError("caption timestamp is invalid")
    hours, minutes, seconds, fraction = (int(part) for part in match.groups())
    scale = 100 if centiseconds else 1000
    if len(match.group(4)) != (2 if centiseconds else 3):
        raise ValueError("caption timestamp precision is invalid")
    total = ((hours * 60 + minutes) * 60 + seconds) * scale + fraction
    return Fraction(total, scale)


def serialize_srt(document: Mapping[str, Any]) -> str:
    """Serialize captions as HTML-escaped plain-text SRT with millisecond times."""
    fps = Fraction(str(document["fps"]))
    blocks: list[str] = []
    for index, caption in enumerate(document.get("captions", []), start=1):
        start = _format_timestamp(_frame_milliseconds(caption["start_frame"], fps), ",")
        end = _format_timestamp(_frame_milliseconds(caption["end_frame"], fps), ",")
        text = html.escape(str(caption["text"]), quote=False)
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def parse_srt(value: str, fps_text: str) -> list[dict[str, Any]]:
    """Parse the supported SRT subset and quantize timestamps back to contract frames."""
    fps = Fraction(fps_text)
    captions: list[dict[str, Any]] = []
    for block in re.split(r"\r?\n\s*\r?\n", value.strip()):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            continue
        timing = lines[1].split(" --> ", 1)
        if len(timing) != 2:
            raise ValueError("SRT timing line is invalid")
        start, end = (_parse_timestamp(item, centiseconds=False) for item in timing)
        captions.append(
            {
                "start_frame": time_to_frame(start, fps),
                "end_frame": time_to_frame(end, fps),
                "text": html.unescape("\n".join(lines[2:])),
            }
        )
    return captions


def _strip_ass_overrides(value: str) -> str:
    """Remove emitted override blocks while preserving escaped literal braces."""
    output: list[str] = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value) and value[index + 1] in "\\{}N":
            output.extend((value[index], value[index + 1]))
            index += 2
            continue
        if value[index] == "{" and index + 1 < len(value) and value[index + 1] == "\\":
            close = value.find("}", index + 2)
            if close >= 0:
                index = close + 1
                continue
        output.append(value[index])
        index += 1
    return _ass_unescape_text("".join(output))


def _ass_escape_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def _ass_unescape_text(value: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            following = value[index + 1]
            if following == "N":
                output.append("\n")
                index += 2
                continue
            if following in {"\\", "{", "}"}:
                output.append(following)
                index += 2
                continue
        output.append(value[index])
        index += 1
    return "".join(output)


def _emphasized_ass_text(caption: Mapping[str, Any]) -> str:
    text = str(caption["text"])
    spans = sorted(caption.get("emphasis", []), key=lambda item: item["start_codepoint"])
    output: list[str] = []
    cursor = 0
    for span in spans:
        start, end = span["start_codepoint"], span["end_codepoint"]
        if (
            type(start) is not int
            or type(end) is not int
            or start < cursor
            or end > len(text)
            or end <= start
        ):
            raise ValueError("caption emphasis range is invalid")
        mode = span.get("mode")
        opening = {
            "bold": r"{\b1}",
            "italic": r"{\i1}",
            "uppercase": r"{\b1}",
            "highlight": r"{\b1\u1}",
        }.get(mode)
        closing = {
            "bold": r"{\b0}",
            "italic": r"{\i0}",
            "uppercase": r"{\b0}",
            "highlight": r"{\b0\u0}",
        }.get(mode)
        if opening is None or closing is None:
            raise ValueError("caption emphasis mode is invalid")
        output.append(_ass_escape_text(text[cursor:start]))
        output.extend((opening, _ass_escape_text(text[start:end]), closing))
        cursor = end
    output.append(_ass_escape_text(text[cursor:]))
    return "".join(output)


def _ass_color(color: str) -> str:
    rgb = color.removeprefix("#").upper()
    if not re.fullmatch(r"[0-9A-F]{6}", rgb):
        raise ValueError("speaker color is invalid")
    red, green, blue = rgb[:2], rgb[2:4], rgb[4:]
    return f"&H00{blue}{green}{red}"


def serialize_ass(
    document: Mapping[str, Any],
    speakers_document: Mapping[str, Any],
    config: CaptionConfig,
) -> str:
    """Serialize ASS styles using only speakers.json colors and configured layout values."""
    config.validate()
    fps = Fraction(str(document["fps"]))
    speaker_keys = sorted({caption["speaker_key"] for caption in document.get("captions", [])})
    styles = [
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, "
        "MarginV, Encoding"
    ]
    for speaker_key in speaker_keys:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", speaker_key):
            raise ValueError("caption speaker key is invalid")
        color = resolve_speaker_color(speakers_document, speaker_key)
        style_name = f"speaker_{speaker_key}"
        styles.append(
            "Style: "
            + ",".join(
                [
                    style_name,
                    config.font_name,
                    str(config.font_size),
                    _ass_color(color),
                    _ass_color(color),
                    _ass_color(config.outline_color),
                    "&H00000000",
                    "0",
                    "0",
                    "0",
                    "0",
                    "100",
                    "100",
                    "0",
                    "0",
                    "1",
                    f"{config.outline_width:g}",
                    "0",
                    "2",
                    "48",
                    "48",
                    str(config.margin_v),
                    "1",
                ]
            )
        )
    events = ["Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for caption in document.get("captions", []):
        start = _format_timestamp(_frame_centiseconds(caption["start_frame"], fps), ".")
        end = _format_timestamp(_frame_centiseconds(caption["end_frame"], fps), ".")
        style_name = f"speaker_{caption['speaker_key']}"
        dialogue_text = _emphasized_ass_text(caption)
        events.append(
            f"Dialogue: 0,{start},{end},{style_name},,0,0,{config.margin_v},,{dialogue_text}"
        )
    sections = [
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 2\nScaledBorderAndShadow: yes",
        "[V4+ Styles]\n" + "\n".join(styles),
        "[Events]\n" + "\n".join(events),
    ]
    return "\n\n".join(sections) + "\n"


def parse_ass(value: str, fps_text: str) -> list[dict[str, Any]]:
    """Parse serialized Dialogue rows and quantize ASS centiseconds to contract frames."""
    fps = Fraction(fps_text)
    captions: list[dict[str, Any]] = []
    in_events = False
    for line in value.splitlines():
        if line.strip() == "[Events]":
            in_events = True
            continue
        if line.startswith("[") and line.strip() != "[Events]":
            in_events = False
        if not in_events or not line.startswith("Dialogue: "):
            continue
        fields = line[len("Dialogue: ") :].split(",", 9)
        if len(fields) != 10:
            raise ValueError("ASS dialogue row is invalid")
        start = _parse_timestamp(fields[1], centiseconds=True)
        end = _parse_timestamp(fields[2], centiseconds=True)
        stripped = _strip_ass_overrides(fields[9])
        captions.append(
            {
                "start_frame": time_to_frame(start, fps),
                "end_frame": time_to_frame(end, fps),
                "text": _ass_unescape_text(stripped),
            }
        )
    return captions


class SidecarOnlyRenderer:
    """Write contract JSON, SRT, ASS, and the text-free caption report."""

    def write_sidecars(
        self,
        output_dir: str | Path,
        document: Mapping[str, Any],
        report: Mapping[str, Any],
        speakers_document: Mapping[str, Any],
        config: CaptionConfig,
    ) -> tuple[Path, Path, Path, Path]:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        json_path, srt_path = root / "captions.json", root / "captions.srt"
        ass_path, report_path = root / "captions.ass", root / "captions_report.json"
        json_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        srt_path.write_text(serialize_srt(document), encoding="utf-8")
        ass_path.write_text(serialize_ass(document, speakers_document, config), encoding="utf-8")
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return json_path, srt_path, ass_path, report_path


class AssBurnInRenderer(SidecarOnlyRenderer):
    """Apply a generated ASS sidecar to a confined rendered-video copy with local FFmpeg."""

    def burn_in(
        self,
        video_path: str | Path,
        ass_path: str | Path,
        output_path: str | Path,
        *,
        allowed_root: str | Path,
        timeout_s: int = 3600,
    ) -> Path:
        root = Path(allowed_root).resolve()
        video = Path(video_path).resolve()
        ass = Path(ass_path).resolve()
        output = Path(output_path).resolve()
        if any(not path.is_relative_to(root) for path in (video, ass, output)):
            raise CaptionRenderError("caption burn-in paths must stay inside the job directory")
        if not video.is_file() or not ass.is_file() or output == video:
            raise CaptionRenderError("caption burn-in inputs are invalid")
        executable = shutil.which("ffmpeg")
        if executable is None:
            raise CaptionRenderUnavailable("ffmpeg is unavailable; ASS sidecars remain usable")
        escaped_ass = str(ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        video_filter = f"subtitles='{escaped_ass}'"
        try:
            result = subprocess.run(
                [
                    executable,
                    "-hide_banner",
                    "-nostdin",
                    "-n",
                    "-i",
                    str(video),
                    "-vf",
                    video_filter,
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "copy",
                    str(output),
                ],
                cwd=root,
                capture_output=True,
                check=False,
                shell=False,
                timeout=timeout_s,
                env=safe_child_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            raise CaptionRenderError("caption burn-in process could not complete") from None
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise CaptionRenderError("caption burn-in failed; inspect local FFmpeg support")
        return output
