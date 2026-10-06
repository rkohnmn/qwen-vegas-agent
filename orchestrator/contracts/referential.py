"""Pure semantic and cross-document validation checks."""

from __future__ import annotations

import math
import ntpath
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .errors import ErrorCode, ValidationIssue
from .hashing import hash_words

_CATALOG_GROUPS = ("transitions", "video_fx", "audio_fx", "text_presets", "sfx")
_PATH_FIELDS = {
    "working_copy_path",
    "file_path",
    "asset_path",
    "output_path",
    "project_path",
}
_FRAME_FIELDS = {
    "frame",
    "start_frame",
    "end_frame",
    "at_frame",
    "from_frame",
    "frame_count",
    "frames",
    "length_frames",
    "take_offset_frames",
    "duration_frames",
}
_REFERENCE_FIELDS = {
    "event_id",
    "left_event_id",
    "right_event_id",
    "target_id",
    "marker_id",
    "region_id",
}


def _issue(code: ErrorCode, path: str, message: str) -> ValidationIssue:
    return ValidationIssue(code, path, message)


def _ids(document: Mapping[str, Any], member: str) -> set[str]:
    values = document.get(member, [])
    if not isinstance(values, list):
        return set()
    return {
        item["id"]
        for item in values
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }


def check_words(words: Mapping[str, Any]) -> list[ValidationIssue]:
    """Check time ordering, uniqueness, and segment/gap references."""
    issues: list[ValidationIssue] = []
    word_rows = words.get("words", [])
    if not isinstance(word_rows, list):
        return [_issue(ErrorCode.E_SCHEMA, "words", "words must be an array")]
    word_indices: dict[str, int] = {}
    previous_start: float | None = None
    for index, word in enumerate(word_rows):
        path = f"words[{index}]"
        if not isinstance(word, Mapping):
            issues.append(_issue(ErrorCode.E_SCHEMA, path, "word must be an object"))
            continue
        word_id = word.get("id")
        if isinstance(word_id, str):
            if word_id in word_indices:
                issues.append(
                    _issue(ErrorCode.E_DUPLICATE_ID, f"{path}.id", "word ID is duplicated")
                )
            else:
                word_indices[word_id] = index
        start = word.get("start")
        end = word.get("end")
        if (
            not isinstance(start, int | float)
            or isinstance(start, bool)
            or not isinstance(end, int | float)
            or isinstance(end, bool)
            or not math.isfinite(float(start))
            or not math.isfinite(float(end))
        ):
            issues.append(_issue(ErrorCode.E_SCHEMA, path, "word times must be finite numbers"))
            continue
        if end < start:
            issues.append(_issue(ErrorCode.E_WORD_TIME, path, "word end precedes its start"))
        if previous_start is not None and start < previous_start:
            issues.append(_issue(ErrorCode.E_WORD_ORDER, path, "word times are not monotonic"))
        previous_start = float(start)

    valid_word_ids = set(word_indices)
    for index, segment in enumerate(words.get("segments", [])):
        if not isinstance(segment, Mapping):
            continue
        for word_index, word_id in enumerate(segment.get("word_ids", [])):
            if word_id not in valid_word_ids:
                issues.append(
                    _issue(
                        ErrorCode.E_REF_WORD,
                        f"segments[{index}].word_ids[{word_index}]",
                        "segment references a missing word",
                    )
                )

    seen_gap_ids: set[str] = set()
    for index, gap in enumerate(words.get("gaps", [])):
        if not isinstance(gap, Mapping):
            continue
        gap_id = gap.get("id")
        if isinstance(gap_id, str):
            if gap_id in seen_gap_ids or gap_id in valid_word_ids:
                issues.append(
                    _issue(
                        ErrorCode.E_DUPLICATE_ID, f"gaps[{index}].id", "document ID is duplicated"
                    )
                )
            seen_gap_ids.add(gap_id)
        start = gap.get("start")
        end = gap.get("end")
        if (
            isinstance(start, int | float)
            and not isinstance(start, bool)
            and isinstance(end, int | float)
            and not isinstance(end, bool)
            and end < start
        ):
            issues.append(
                _issue(ErrorCode.E_WORD_TIME, f"gaps[{index}]", "gap end precedes its start")
            )
    return issues


def check_catalog(catalog: Mapping[str, Any]) -> list[ValidationIssue]:
    """Reject collisions across all catalog groups."""
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for group in _CATALOG_GROUPS:
        for index, entry in enumerate(catalog.get(group, [])):
            if not isinstance(entry, Mapping):
                continue
            key = entry.get("key")
            if isinstance(key, str):
                if key in seen:
                    issues.append(
                        _issue(
                            ErrorCode.E_DUPLICATE_CATALOG_KEY,
                            f"{group}[{index}].key",
                            "catalog key is duplicated",
                        )
                    )
                seen.add(key)
    return issues


def _catalog_keys(catalog: Mapping[str, Any]) -> set[str]:
    return {
        entry["key"]
        for group in _CATALOG_GROUPS
        for entry in catalog.get(group, [])
        if isinstance(entry, Mapping) and isinstance(entry.get("key"), str)
    }


def _anchor_reference(
    anchor: Mapping[str, Any],
    path: str,
    word_ids: set[str],
    segment_ids: set[str],
    gap_ids: set[str],
    cut_ids: set[str],
    event_ids: set[str] | None,
) -> list[ValidationIssue]:
    kind = anchor.get("kind")
    value = anchor.get("id")
    if not isinstance(kind, str) or not isinstance(value, str):
        return []
    targets: dict[str, tuple[set[str], ErrorCode, str]] = {
        "word": (word_ids, ErrorCode.E_REF_WORD, "word"),
        "segment": (segment_ids, ErrorCode.E_REF_SEGMENT, "segment"),
        "gap": (gap_ids, ErrorCode.E_REF_GAP, "gap"),
        "cut": (cut_ids, ErrorCode.E_REF_CUT, "cut"),
    }
    if kind in targets:
        known, code, label = targets[kind]
        if value not in known:
            return [_issue(code, path, f"anchor references a missing {label}")]
    if kind == "event" and event_ids is not None and value not in event_ids:
        return [_issue(ErrorCode.E_REF_EVENT, path, "anchor references a missing event")]
    return []


def check_edl_against(
    edl: Mapping[str, Any],
    words: Mapping[str, Any],
    speakers: Mapping[str, Any],
    catalog: Mapping[str, Any],
    timeline: Mapping[str, Any] | None = None,
) -> list[ValidationIssue]:
    """Check hashes and every word, segment, gap, speaker, cut, and catalog ref."""
    issues: list[ValidationIssue] = []
    if edl.get("words_hash") != hash_words(dict(words)):
        issues.append(_issue(ErrorCode.E_WORDS_HASH, "words_hash", "words hash does not match"))

    word_rows = words.get("words", [])
    word_ids: set[str] = set()
    word_index: dict[str, int] = {}
    for index, row in enumerate(word_rows):
        if not isinstance(row, Mapping):
            continue
        word_id = row.get("id")
        if isinstance(word_id, str):
            word_ids.add(word_id)
            word_index[word_id] = index
    segment_ids = _ids(words, "segments")
    gap_ids = _ids(words, "gaps")
    known_speakers = set(speakers.get("speakers", {}).keys())
    catalog_keys = _catalog_keys(catalog)
    cut_rows = edl.get("cuts", [])
    cut_ids: set[str] = set()
    for cut in cut_rows:
        if not isinstance(cut, Mapping):
            continue
        cut_id = cut.get("id")
        if isinstance(cut_id, str):
            cut_ids.add(cut_id)
    event_ids = _ids(timeline, "events") if timeline is not None else None

    ranges: list[tuple[int, int, int]] = []
    for index, cut in enumerate(cut_rows):
        if not isinstance(cut, Mapping):
            continue
        remove = cut.get("remove", {})
        if not isinstance(remove, Mapping):
            continue
        from_word = remove.get("from_word")
        to_word = remove.get("to_word")
        from_index = word_index.get(from_word) if isinstance(from_word, str) else None
        to_index = word_index.get(to_word) if isinstance(to_word, str) else None
        if from_index is None:
            issues.append(
                _issue(
                    ErrorCode.E_REF_WORD,
                    f"cuts[{index}].remove.from_word",
                    "cut references a missing word",
                )
            )
        if to_index is None:
            issues.append(
                _issue(
                    ErrorCode.E_REF_WORD,
                    f"cuts[{index}].remove.to_word",
                    "cut references a missing word",
                )
            )
        if from_index is not None and to_index is not None:
            if from_index > to_index:
                issues.append(
                    _issue(ErrorCode.E_CUT_ORDER, f"cuts[{index}].remove", "cut range is reversed")
                )
            else:
                ranges.append((from_index, to_index, index))

    ranges.sort()
    furthest_end = -1
    for start, end, index in ranges:
        if start <= furthest_end:
            issues.append(
                _issue(ErrorCode.E_CUT_OVERLAP, f"cuts[{index}].remove", "cut overlaps another cut")
            )
        furthest_end = max(furthest_end, end)

    def check_word_ref(value: Any, path: str) -> None:
        if isinstance(value, str) and value not in word_ids:
            issues.append(_issue(ErrorCode.E_REF_WORD, path, "reference points to a missing word"))

    def check_catalog_ref(value: Any, path: str) -> None:
        if isinstance(value, str) and value not in catalog_keys:
            issues.append(
                _issue(ErrorCode.E_REF_CATALOG, path, "reference points to a missing catalog key")
            )

    for index, transition in enumerate(edl.get("transitions", [])):
        if not isinstance(transition, Mapping):
            continue
        if transition.get("at_cut") not in cut_ids:
            issues.append(
                _issue(
                    ErrorCode.E_REF_CUT,
                    f"transitions[{index}].at_cut",
                    "transition references a missing cut",
                )
            )
        check_catalog_ref(transition.get("type"), f"transitions[{index}].type")

    for index, item in enumerate(edl.get("sfx", [])):
        if isinstance(item, Mapping):
            check_word_ref(item.get("at_word"), f"sfx[{index}].at_word")
            check_catalog_ref(item.get("key"), f"sfx[{index}].key")

    subtitles = edl.get("subtitles", {})
    if isinstance(subtitles, Mapping):
        check_catalog_ref(subtitles.get("style"), "subtitles.style")
        for index, item in enumerate(subtitles.get("emphasis", [])):
            if not isinstance(item, Mapping):
                continue
            for word_index_value, word_id in enumerate(item.get("word_ids", [])):
                check_word_ref(
                    word_id,
                    f"subtitles.emphasis[{index}].word_ids[{word_index_value}]",
                )
        for index, item in enumerate(subtitles.get("break_hints", [])):
            if isinstance(item, Mapping):
                check_word_ref(
                    item.get("before_word"),
                    f"subtitles.break_hints[{index}].before_word",
                )
        for index, item in enumerate(subtitles.get("omit_ranges", [])):
            if isinstance(item, Mapping):
                check_word_ref(
                    item.get("from_word"),
                    f"subtitles.omit_ranges[{index}].from_word",
                )
                check_word_ref(
                    item.get("to_word"),
                    f"subtitles.omit_ranges[{index}].to_word",
                )

    for index, question in enumerate(edl.get("questions", [])):
        if not isinstance(question, Mapping):
            continue
        speaker_key = question.get("speaker_key")
        if isinstance(speaker_key, str) and speaker_key not in known_speakers:
            issues.append(
                _issue(
                    ErrorCode.E_REF_SPEAKER,
                    f"questions[{index}].speaker_key",
                    "question references an unknown speaker",
                )
            )

    for index, request in enumerate(edl.get("tool_requests", [])):
        if not isinstance(request, Mapping):
            continue
        anchor = request.get("anchor")
        if isinstance(anchor, Mapping):
            issues.extend(
                _anchor_reference(
                    anchor,
                    f"tool_requests[{index}].anchor",
                    word_ids,
                    segment_ids,
                    gap_ids,
                    cut_ids,
                    event_ids,
                )
            )
    return issues


def _frame_issues(value: Any, path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in _FRAME_FIELDS:
                values = child if isinstance(child, list) else [child]
                if any(type(frame) is not int or frame < 0 for frame in values):
                    issues.append(
                        _issue(
                            ErrorCode.E_FRAME_TYPE,
                            child_path,
                            "frame values must be non-negative integers",
                        )
                    )
            else:
                issues.extend(_frame_issues(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_frame_issues(child, f"{path}[{index}]"))
    return issues


def _path_is_within(candidate_value: str, root_value: str | Path) -> bool:
    candidate_text = candidate_value.strip()
    root_text = str(root_value)
    candidate_windows = PureWindowsPath(candidate_text)
    root_windows = PureWindowsPath(root_text)
    candidate_posix = PurePosixPath(candidate_text)
    windows_mode = bool(
        candidate_windows.drive or root_windows.drive or candidate_text.startswith("\\\\")
    )
    if windows_mode:
        if (
            candidate_posix.is_absolute()
            and not candidate_windows.drive
            and candidate_text.startswith("/")
        ):
            return False
        if not root_windows.drive:
            return False
        normalized_root = PureWindowsPath(ntpath.normpath(root_text))
        if candidate_windows.drive or candidate_text.startswith("\\\\"):
            normalized_candidate = PureWindowsPath(ntpath.normpath(candidate_text))
        else:
            normalized_candidate = PureWindowsPath(
                ntpath.normpath(str(normalized_root / candidate_text))
            )
        return normalized_candidate == normalized_root or normalized_candidate.is_relative_to(
            normalized_root
        )

    root_path = Path(root_text).resolve(strict=False)
    candidate_path = Path(candidate_text)
    if not candidate_path.is_absolute():
        candidate_path = root_path / candidate_path
    return candidate_path.resolve(strict=False).is_relative_to(root_path)


def check_ops(ops: Mapping[str, Any], working_dir: str | Path) -> list[ValidationIssue]:
    """Check path confinement, exact frames, and operation creation order."""
    operations = ops.get("operations", [])
    if not isinstance(operations, list):
        return [_issue(ErrorCode.E_SCHEMA, "operations", "operations must be an array")]
    issues = _frame_issues(ops, "$")

    header = ops.get("header", {})
    working_copy = header.get("working_copy_path") if isinstance(header, Mapping) else None
    if isinstance(working_copy, str) and not _path_is_within(working_copy, working_dir):
        issues.append(
            _issue(
                ErrorCode.E_PATH_CONFINEMENT,
                "header.working_copy_path",
                "path escapes the working directory",
            )
        )

    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping):
            continue
        for path_field in _PATH_FIELDS - {"working_copy_path"}:
            value = operation.get(path_field)
            if isinstance(value, str) and not _path_is_within(value, working_dir):
                issues.append(
                    _issue(
                        ErrorCode.E_PATH_CONFINEMENT,
                        f"operations[{index}].{path_field}",
                        "path escapes the working directory",
                    )
                )

    creators: dict[str, int] = {}
    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping):
            continue
        op = operation.get("op")
        for field in ("marker_id", "region_id", "event_id"):
            identifier = operation.get(field)
            creates = (
                (field == "marker_id" and op == "add_marker")
                or (field == "region_id" and op == "add_region")
                or (field == "event_id" and op in {"add_audio_event", "add_text_event"})
            )
            if creates and isinstance(identifier, str):
                creators[identifier] = index

    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping):
            continue
        for field in _REFERENCE_FIELDS:
            identifier = operation.get(field)
            if (
                isinstance(identifier, str)
                and identifier in creators
                and creators[identifier] > index
            ):
                issues.append(
                    _issue(
                        ErrorCode.E_OP_ORDER,
                        f"operations[{index}].{field}",
                        "operation references an entity created later",
                    )
                )
    return issues
