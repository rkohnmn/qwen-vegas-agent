from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any

from orchestrator.compiler import FrameInterval, ceil_fraction, kept_intervals, time_to_frame

_PUNCTUATION = frozenset(",.;:!?%)]}»”’、。？！…")
_OPENING = frozenset("([{«“‘")
_EDGE_PUNCTUATION = " \t\r\n.,!?;:()[]{}\"'“”‘’«»、。？！…"
_DEFAULT_FILLERS = frozenset({"uh", "um", "erm", "er", "hmm", "mm"})


@dataclass(frozen=True, slots=True)
class CaptionConfig:
    """Deterministic caption-layout and display-policy settings."""

    max_chars_per_line: int = 42
    max_lines: int = 2
    max_cps: float = 20.0
    min_duration_ms: int = 700
    hold_ms: int = 100
    low_speaker_conf_threshold: float = 0.65
    show_fillers: bool = True
    filler_words: tuple[str, ...] = tuple(sorted(_DEFAULT_FILLERS))
    profanity_policy: str = "keep"
    profanity_words: tuple[str, ...] = ()
    renderer: str = "ass_burn_in"
    font_name: str = "Arial"
    font_size: int = 48
    outline_color: str = "#000000"
    outline_width: float = 2.0
    margin_v: int = 48
    minimum_contrast_ratio: float = 3.0

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> CaptionConfig:
        """Read only the caption subsection; absent optional settings use documented defaults."""
        return cls(
            max_chars_per_line=int(values.get("max_chars_per_line", 42)),
            max_lines=int(values.get("max_lines", 2)),
            max_cps=float(values.get("max_cps", 20.0)),
            min_duration_ms=int(values.get("min_duration_ms", 700)),
            hold_ms=int(values.get("hold_ms", 100)),
            low_speaker_conf_threshold=float(values.get("low_speaker_conf_threshold", 0.65)),
            show_fillers=bool(values.get("show_fillers", True)),
            filler_words=tuple(
                str(item) for item in values.get("filler_words", sorted(_DEFAULT_FILLERS))
            ),
            profanity_policy=str(values.get("profanity_policy", "keep")),
            profanity_words=tuple(str(item) for item in values.get("profanity_words", ())),
            renderer=str(values.get("renderer", "ass_burn_in")),
            font_name=str(values.get("font_name", "Arial")),
            font_size=int(values.get("font_size", 48)),
            outline_color=str(values.get("outline_color", "#000000")),
            outline_width=float(values.get("outline_width", 2.0)),
            margin_v=int(values.get("margin_v", 48)),
            minimum_contrast_ratio=float(values.get("minimum_contrast_ratio", 3.0)),
        )

    def validate(self) -> None:
        if not 1 <= self.max_chars_per_line <= 200 or not 1 <= self.max_lines <= 8:
            raise ValueError("caption line limits are invalid")
        if not math.isfinite(self.max_cps) or not 1 <= self.max_cps <= 100:
            raise ValueError("caption reading-speed limit is invalid")
        if self.min_duration_ms < 1 or self.hold_ms < 0:
            raise ValueError("caption duration settings are invalid")
        if not 0 <= self.low_speaker_conf_threshold <= 1:
            raise ValueError("caption confidence threshold is invalid")
        if self.profanity_policy not in {"keep", "mask", "omit"}:
            raise ValueError("caption profanity policy is invalid")
        if self.renderer not in {
            "ass_burn_in",
            "sidecar_only",
            "direct_color",
            "preset_per_speaker",
        }:
            raise ValueError("caption renderer is invalid")
        if not self.font_name or any(character in self.font_name for character in ",[]\r\n"):
            raise ValueError("caption font name is invalid")
        if not 8 <= self.font_size <= 200 or not 0 <= self.margin_v <= 500:
            raise ValueError("caption font metrics are invalid")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", self.outline_color):
            raise ValueError("caption outline color is invalid")
        if not math.isfinite(self.outline_width) or not 0 <= self.outline_width <= 20:
            raise ValueError("caption outline width is invalid")
        if (
            not math.isfinite(self.minimum_contrast_ratio)
            or not 1 <= self.minimum_contrast_ratio <= 21
        ):
            raise ValueError("caption contrast limit is invalid")


@dataclass(frozen=True, slots=True)
class _Word:
    word_id: str
    speaker_key: str
    text: str
    source_start: int
    source_end: int
    start: int
    end: int
    confidence: float
    overlap: bool
    unknown_speaker: bool
    profanity_masked: bool
    emphasis: str | None
    break_before: bool


def grapheme_clusters(value: str) -> list[str]:
    """Group combining marks, joiners, flags, emoji modifiers, and Hangul jamo safely."""
    if not value:
        return []
    clusters: list[str] = []
    regional_count = 0
    for character in value:
        codepoint = ord(character)
        category = unicodedata.category(character)
        previous = clusters[-1][-1] if clusters else ""
        previous_codepoint = ord(previous) if previous else -1
        is_regional = 0x1F1E6 <= codepoint <= 0x1F1FF
        previous_is_regional = 0x1F1E6 <= previous_codepoint <= 0x1F1FF
        attach = bool(clusters) and (
            category.startswith("M")
            or 0xFE00 <= codepoint <= 0xFE0F
            or 0xE0100 <= codepoint <= 0xE01EF
            or 0x1F3FB <= codepoint <= 0x1F3FF
            or character == "\u200d"
            or previous == "\u200d"
            or (is_regional and previous_is_regional and regional_count % 2 == 1)
            or _hangul_composes(previous_codepoint, codepoint)
            or ("VIRAMA" in unicodedata.name(previous, "") and category.startswith("L"))
        )
        if attach:
            clusters[-1] += character
        else:
            clusters.append(character)
        regional_count = regional_count + 1 if is_regional else 0
    return clusters


def _hangul_type(codepoint: int) -> str:
    if 0x1100 <= codepoint <= 0x115F or 0xA960 <= codepoint <= 0xA97C:
        return "L"
    if 0x1160 <= codepoint <= 0x11A7 or 0xD7B0 <= codepoint <= 0xD7C6:
        return "V"
    if 0x11A8 <= codepoint <= 0x11FF or 0xD7CB <= codepoint <= 0xD7FB:
        return "T"
    if 0xAC00 <= codepoint <= 0xD7A3:
        return "LV" if (codepoint - 0xAC00) % 28 == 0 else "LVT"
    return ""


def _hangul_composes(previous: int, current: int) -> bool:
    left, right = _hangul_type(previous), _hangul_type(current)
    return (
        (left == "L" and right in {"L", "V", "LV", "LVT"})
        or (left in {"LV", "V"} and right in {"V", "T"})
        or (left in {"LVT", "T"} and right == "T")
    )


def _normalized_word(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip(_EDGE_PUNCTUATION)


def _word_order(words: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    source_rows = words.get("words", [])
    if not isinstance(source_rows, list):
        raise ValueError("words document is invalid")
    rows = [row for row in source_rows if isinstance(row, dict) and isinstance(row.get("id"), str)]
    return rows, {row["id"]: index for index, row in enumerate(rows)}


def _omitted_word_ids(
    edl: Mapping[str, Any], rows: list[dict[str, Any]], indices: dict[str, int]
) -> tuple[set[str], list[dict[str, str]]]:
    omitted: set[str] = set()
    warnings: list[dict[str, str]] = []
    subtitles = edl.get("subtitles", {})
    ranges = subtitles.get("omit_ranges", []) if isinstance(subtitles, Mapping) else []
    for range_index, item in enumerate(ranges if isinstance(ranges, list) else []):
        if not isinstance(item, Mapping):
            continue
        first, last = item.get("from_word"), item.get("to_word")
        if first not in indices or last not in indices or indices[first] > indices[last]:
            warnings.append({"code": "W_OMIT_RANGE_INVALID", "range_index": str(range_index)})
            continue
        omitted.update(row["id"] for row in rows[indices[first] : indices[last] + 1])
    return omitted, warnings


def _emphasis_by_word(edl: Mapping[str, Any]) -> dict[str, str]:
    subtitles = edl.get("subtitles", {})
    spans = subtitles.get("emphasis", []) if isinstance(subtitles, Mapping) else []
    result: dict[str, str] = {}
    for span in spans if isinstance(spans, list) else []:
        if not isinstance(span, Mapping):
            continue
        mode, ids = span.get("mode"), span.get("word_ids", [])
        if mode not in {"bold", "italic", "uppercase", "highlight"} or not isinstance(ids, list):
            continue
        for word_id in ids:
            if isinstance(word_id, str):
                result[word_id] = str(mode)
    return result


def _mapped_word_range(
    start_seconds: int | float,
    end_seconds: int | float,
    fps: Fraction,
    keep: list[tuple[int, int]],
) -> tuple[int, int, int, int] | None:
    source_start = max(0, time_to_frame(Fraction(str(start_seconds)), fps))
    source_end = time_to_frame(Fraction(str(end_seconds)), fps, rounding="ceil")
    source_end = max(source_start + 1, source_end)
    offset = 0
    for keep_start, keep_end in keep:
        if keep_start <= source_start and source_end <= keep_end:
            return (
                source_start,
                source_end,
                offset + source_start - keep_start,
                offset + source_end - keep_start,
            )
        offset += keep_end - keep_start
    return None


def _split_long_word(word: _Word, max_chars: int) -> list[_Word]:
    clusters = grapheme_clusters(word.text)
    return [
        replace(word, text="".join(clusters[index : index + max_chars]))
        for index in range(0, len(clusters), max_chars)
    ] or [word]


def _joiner(previous: str, current: str, same_word: bool) -> str:
    if not previous or same_word:
        return ""
    first = grapheme_clusters(current)[0] if current else ""
    last = grapheme_clusters(previous)[-1] if previous else ""
    if first in _PUNCTUATION or last in _OPENING:
        return ""
    return " "


def _render_line(parts: Sequence[_Word]) -> tuple[str, list[dict[str, Any]]]:
    text = ""
    emphasis: list[dict[str, Any]] = []
    previous_part: _Word | None = None
    for part in parts:
        rendered = part.text.upper() if part.emphasis == "uppercase" else part.text
        separator = _joiner(
            previous_part.text if previous_part else "",
            rendered,
            bool(previous_part and previous_part.word_id == part.word_id),
        )
        start = len(text) + len(separator)
        text += separator + rendered
        end = len(text)
        if part.emphasis is not None and end > start:
            emphasis.append(
                {
                    "word_ids": [part.word_id],
                    "mode": part.emphasis,
                    "start_codepoint": start,
                    "end_codepoint": end,
                }
            )
        previous_part = part
    return text, emphasis


def _wrap_lines(parts: Sequence[_Word], config: CaptionConfig) -> list[list[_Word]]:
    lines: list[list[_Word]] = [[]]
    for word in parts:
        for piece in _split_long_word(word, config.max_chars_per_line):
            current = lines[-1]
            candidate = [*current, piece]
            candidate_text, _ = _render_line(candidate)
            current_text, _ = _render_line(current)
            prefer_break = (
                bool(current)
                and len(grapheme_clusters(current_text)) >= config.max_chars_per_line * 0.55
                and current_text.rstrip().endswith(tuple(_PUNCTUATION))
            )
            if current and (
                len(grapheme_clusters(candidate_text)) > config.max_chars_per_line or prefer_break
            ):
                if len(lines) < config.max_lines:
                    lines.append([piece])
                else:
                    lines.append([piece])
            else:
                current.append(piece)
    return [line for line in lines if line]


def _group_text(
    parts: Sequence[_Word], config: CaptionConfig
) -> tuple[str, list[dict[str, Any]], int]:
    lines = _wrap_lines(parts, config)
    rendered_lines: list[str] = []
    emphasis: list[dict[str, Any]] = []
    offset = 0
    maximum_lines = len(lines)
    for line_index, line in enumerate(lines):
        line_text, line_emphasis = _render_line(line)
        rendered_lines.append(line_text)
        for span in line_emphasis:
            emphasis.append(
                {
                    **span,
                    "start_codepoint": span["start_codepoint"] + offset,
                    "end_codepoint": span["end_codepoint"] + offset,
                }
            )
        offset += len(line_text) + (1 if line_index < len(lines) - 1 else 0)
    return "\n".join(rendered_lines), emphasis, maximum_lines


def _caption_for_group(
    parts: Sequence[_Word],
    *,
    caption_id: str,
    style_key: str | None,
    fps: Fraction,
    duration_frames: int,
    config: CaptionConfig,
) -> tuple[dict[str, Any], dict[str, Any]]:
    text, emphasis, line_count = _group_text(parts, config)
    start = min(part.start for part in parts)
    last_word_end = max(part.end for part in parts)
    hold = ceil_fraction(Fraction(config.hold_ms, 1000) * fps)
    minimum = ceil_fraction(Fraction(config.min_duration_ms, 1000) * fps)
    end = min(duration_frames, max(last_word_end + hold, start + minimum))
    if end <= start:
        end = min(duration_frames, start + 1)
    flags: set[str] = set()
    if any(part.confidence < config.low_speaker_conf_threshold for part in parts):
        flags.add("low_speaker_conf")
    if any(part.overlap for part in parts):
        flags.add("overlap")
    if any(part.unknown_speaker or part.speaker_key.startswith("unknown_") for part in parts):
        flags.add("unknown_speaker")
    if any(part.profanity_masked for part in parts):
        flags.add("profanity_masked")
    source_ids = list(dict.fromkeys(part.word_id for part in parts))
    duration_seconds = max(float(Fraction(end - start, 1) / fps), 1 / float(fps))
    cps = len(grapheme_clusters(text.replace("\n", ""))) / duration_seconds
    warnings: list[dict[str, Any]] = []
    if line_count > config.max_lines:
        warnings.append(
            {"code": "W_CAPTION_LINE_COUNT", "caption_id": caption_id, "actual": line_count}
        )
    if cps > config.max_cps:
        warnings.append(
            {"code": "W_CAPTION_CPS", "caption_id": caption_id, "actual": round(cps, 3)}
        )
    if end - start < minimum:
        warnings.append(
            {
                "code": "W_CAPTION_MIN_DURATION",
                "caption_id": caption_id,
                "actual_frames": end - start,
            }
        )
    caption = {
        "id": caption_id,
        "speaker_key": parts[0].speaker_key,
        "text": text,
        "start_frame": start,
        "end_frame": end,
        "style_key": style_key,
        "emphasis": emphasis,
        "confidence_flags": sorted(flags),
        "source_word_ids": source_ids,
    }
    report = {"warnings": warnings, "line_count": line_count, "cps": round(cps, 3)}
    return caption, report


def _removed_between(previous: _Word, current: _Word, removed: Sequence[FrameInterval]) -> bool:
    return any(
        interval.start >= previous.source_end and interval.end <= current.source_start
        for interval in removed
    )


def _rgb(color: str) -> tuple[float, float, float]:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        raise ValueError("speaker color is invalid")
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return linear[0], linear[1], linear[2]


def contrast_ratio(first: str, second: str) -> float:
    """Return the WCAG relative-luminance contrast ratio for two colors."""

    def luminance(color: str) -> float:
        red, green, blue = _rgb(color)
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    first_luminance, second_luminance = luminance(first), luminance(second)
    lighter, darker = max(first_luminance, second_luminance), min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def resolve_speaker_color(speakers_document: Mapping[str, Any], speaker_key: str) -> str:
    """Resolve one caption color only from the validated speakers document."""
    speakers = speakers_document.get("speakers", {})
    if not speaker_key.startswith("unknown_"):
        speaker = speakers.get(speaker_key) if isinstance(speakers, Mapping) else None
        color = speaker.get("color") if isinstance(speaker, Mapping) else None
        if isinstance(color, str):
            return color.upper()
    palette = speakers_document.get("unknown_palette", [])
    if not isinstance(palette, list) or not palette:
        raise ValueError("speaker color palette is missing")
    suffix = speaker_key.removeprefix("unknown_")
    index = int(suffix) - 1 if suffix.isdigit() else 0
    return str(palette[max(0, index) % len(palette)]).upper()


def build_captions(
    words_document: Mapping[str, Any],
    edl: Mapping[str, Any],
    timeline: Mapping[str, Any],
    removed: Sequence[FrameInterval],
    *,
    config: CaptionConfig | None = None,
    speakers_document: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build exact edited-frame captions, splitting on speaker changes and removed cuts."""
    settings = config or CaptionConfig()
    settings.validate()
    fps_text = timeline.get("fps")
    duration = timeline.get("duration_frames")
    if not isinstance(fps_text, str) or type(duration) is not int or duration < 1:
        raise ValueError("caption timeline is invalid")
    fps = Fraction(fps_text)
    keep = kept_intervals(duration, list(removed))
    edited_duration = sum(end - start for start, end in keep)
    if edited_duration < 1:
        raise ValueError("caption timeline contains no retained frames")
    rows, indices = _word_order(words_document)
    omitted_ids, warnings = _omitted_word_ids(edl, rows, indices)
    emphasis_by_word = _emphasis_by_word(edl)
    subtitles = edl.get("subtitles", {})
    style_key = subtitles.get("style") if isinstance(subtitles, Mapping) else None
    if not isinstance(style_key, str):
        style_key = None
    report: dict[str, Any] = {
        "caption_count": 0,
        "source_word_count": len(rows),
        "included_word_count": 0,
        "omitted_edl_word_count": len(omitted_ids),
        "omitted_filler_count": 0,
        "omitted_profanity_count": 0,
        "masked_profanity_count": 0,
        "unaligned_word_count": 0,
        "removed_word_count": 0,
        "warnings": warnings,
        "low_confidence": [],
    }
    speaker_rows = (
        speakers_document.get("speakers", {}) if isinstance(speakers_document, Mapping) else {}
    )
    filler_words = {_normalized_word(item) for item in settings.filler_words}
    profanity_words = {_normalized_word(item) for item in settings.profanity_words}
    tokens: list[_Word] = []
    masked_word_ids: set[str] = set()
    for row in rows:
        word_id = row["id"]
        if word_id in omitted_ids:
            continue
        if row.get("alignment_status", "aligned") != "aligned":
            report["unaligned_word_count"] += 1
            continue
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        normalized = _normalized_word(text)
        if not settings.show_fillers and normalized in filler_words:
            report["omitted_filler_count"] += 1
            continue
        if normalized in profanity_words:
            if settings.profanity_policy == "omit":
                report["omitted_profanity_count"] += 1
                continue
            if settings.profanity_policy == "mask":
                text = "*" * max(1, len(grapheme_clusters(text.strip())))
                report["masked_profanity_count"] += 1
                masked_word_ids.add(word_id)
        start_time, end_time = row.get("start"), row.get("end")
        if not isinstance(start_time, int | float) or isinstance(start_time, bool):
            report["unaligned_word_count"] += 1
            continue
        if not isinstance(end_time, int | float) or isinstance(end_time, bool):
            report["unaligned_word_count"] += 1
            continue
        mapped = _mapped_word_range(start_time, end_time, fps, keep)
        if mapped is None:
            report["removed_word_count"] += 1
            continue
        source_start, source_end, start, end = mapped
        speaker = row.get("speaker")
        speaker_key = speaker if isinstance(speaker, str) else "unknown_1"
        confidence = row.get("speaker_conf", 0.0)
        if not isinstance(confidence, int | float) or isinstance(confidence, bool):
            confidence = 0.0
        tokens.append(
            _Word(
                word_id=word_id,
                speaker_key=speaker_key,
                text=text.strip(),
                source_start=source_start,
                source_end=source_end,
                start=start,
                end=max(start + 1, end),
                confidence=float(confidence),
                overlap=row.get("overlap") is True,
                unknown_speaker=(
                    speaker_key.startswith("unknown_")
                    or (speakers_document is not None and speaker_key not in speaker_rows)
                ),
                profanity_masked=word_id in masked_word_ids,
                emphasis=emphasis_by_word.get(word_id),
                break_before=any(
                    isinstance(item, Mapping) and item.get("before_word") == word_id
                    for item in (
                        subtitles.get("break_hints", []) if isinstance(subtitles, Mapping) else []
                    )
                ),
            )
        )
    tokens.sort(key=lambda item: (item.source_start, item.source_end, indices.get(item.word_id, 0)))
    report["included_word_count"] = len({token.word_id for token in tokens})
    captions: list[dict[str, Any]] = []
    group: list[_Word] = []
    candidate_reports: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal group
        if not group:
            return
        caption_id = f"cap{len(captions) + 1}"
        caption, details = _caption_for_group(
            group,
            caption_id=caption_id,
            style_key=style_key,
            fps=fps,
            duration_frames=edited_duration,
            config=settings,
        )
        captions.append(caption)
        candidate_reports.append(details)
        group = []

    for token in tokens:
        should_flush = bool(group) and (
            token.speaker_key != group[-1].speaker_key
            or token.break_before
            or _removed_between(group[-1], token, removed)
        )
        if should_flush:
            flush()
        candidate = [*group, token]
        candidate_text, _candidate_emphasis, line_count = _group_text(candidate, settings)
        candidate_start = min(part.start for part in candidate)
        candidate_end = min(
            edited_duration,
            max(part.end for part in candidate)
            + ceil_fraction(Fraction(settings.hold_ms, 1000) * fps),
        )
        candidate_end = max(
            candidate_end,
            candidate_start + ceil_fraction(Fraction(settings.min_duration_ms, 1000) * fps),
        )
        candidate_duration = max(
            float(Fraction(candidate_end - candidate_start, 1) / fps), 1 / float(fps)
        )
        candidate_cps = (
            len(grapheme_clusters(candidate_text.replace("\n", ""))) / candidate_duration
        )
        if group and (
            line_count > settings.max_lines
            or candidate_cps > settings.max_cps
            or len({part.word_id for part in candidate}) > 40
        ):
            flush()
        group.append(token)
    flush()

    # Keep every speaker track non-overlapping. If two same-track captions collide at
    # the same first frame, retain the earlier event and report the unplaceable event.
    retained: list[dict[str, Any]] = []
    by_speaker: dict[str, list[dict[str, Any]]] = {}
    for caption in captions:
        by_speaker.setdefault(caption["speaker_key"], []).append(caption)
    dropped_ids: set[str] = set()
    for _speaker, speaker_captions in by_speaker.items():
        ordered = sorted(
            speaker_captions, key=lambda item: (item["start_frame"], item["end_frame"], item["id"])
        )
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if previous["end_frame"] > current["start_frame"]:
                if current["start_frame"] > previous["start_frame"]:
                    previous["end_frame"] = current["start_frame"]
                else:
                    dropped_ids.add(current["id"])
                    report["warnings"].append(
                        {"code": "W_CAPTION_SAME_TRACK_COLLISION", "caption_id": current["id"]}
                    )
    retained = [
        caption
        for caption in captions
        if caption["id"] not in dropped_ids and caption["end_frame"] > caption["start_frame"]
    ]
    retained.sort(key=lambda item: (item["start_frame"], item["speaker_key"], item["id"]))
    caption_details = {
        caption["id"]: details
        for caption, details in zip(captions, candidate_reports, strict=False)
    }
    minimum_frames = ceil_fraction(Fraction(settings.min_duration_ms, 1000) * fps)
    for index, caption in enumerate(retained, start=1):
        original_id = caption["id"]
        caption["id"] = f"cap{index}"
        details = caption_details.get(original_id, {"warnings": [], "line_count": 1, "cps": 0.0})
        for warning in details["warnings"]:
            warning["caption_id"] = caption["id"]
            report["warnings"].append(warning)
        if caption["end_frame"] - caption["start_frame"] < minimum_frames:
            report["warnings"].append(
                {"code": "W_CAPTION_MIN_DURATION", "caption_id": caption["id"]}
            )
        low_flags = {"low_speaker_conf", "overlap", "unknown_speaker"}
        if low_flags.intersection(caption["confidence_flags"]):
            report["low_confidence"].append(
                {
                    "caption_id": caption["id"],
                    "speaker_key": caption["speaker_key"],
                    "start_frame": caption["start_frame"],
                    "end_frame": caption["end_frame"],
                    "source_word_ids": caption["source_word_ids"],
                    "reasons": [flag for flag in caption["confidence_flags"] if flag in low_flags],
                }
            )
    if speakers_document is not None:
        for caption in retained:
            color = resolve_speaker_color(speakers_document, caption["speaker_key"])
            ratio = contrast_ratio(color, settings.outline_color)
            if ratio < settings.minimum_contrast_ratio:
                report["warnings"].append(
                    {
                        "code": "W_CAPTION_LOW_CONTRAST",
                        "caption_id": caption["id"],
                        "speaker_key": caption["speaker_key"],
                        "contrast_ratio": round(ratio, 3),
                    }
                )
    report["caption_count"] = len(retained)
    document = {
        "schema_version": "1.0.0",
        "fps": fps_text,
        "duration_frames": edited_duration,
        "captions": retained,
    }
    return document, report
