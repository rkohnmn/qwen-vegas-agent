"""Pure semantic and cross-document validation checks."""

from __future__ import annotations

import math
import ntpath
from collections.abc import Mapping
from fractions import Fraction
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
        alignment_status = word.get("alignment_status", "aligned")
        if alignment_status == "unaligned":
            if start is not None or end is not None:
                issues.append(
                    _issue(ErrorCode.E_WORD_TIME, path, "unaligned word must not contain times")
                )
            continue
        if (
            not isinstance(start, int | float)
            or isinstance(start, bool)
            or not isinstance(end, int | float)
            or isinstance(end, bool)
            or not math.isfinite(float(start))
            or not math.isfinite(float(end))
        ):
            issues.append(
                _issue(ErrorCode.E_SCHEMA, path, "aligned word times must be finite numbers")
            )
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
    aligned_word_ids: set[str],
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
        if kind == "word" and value not in aligned_word_ids:
            return [
                _issue(
                    ErrorCode.E_WORD_UNALIGNED, path, "anchor uses a word without aligned timing"
                )
            ]
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
    aligned_word_ids: set[str] = set()
    word_index: dict[str, int] = {}
    for index, row in enumerate(word_rows):
        if not isinstance(row, Mapping):
            continue
        word_id = row.get("id")
        if isinstance(word_id, str):
            word_ids.add(word_id)
            if row.get("alignment_status", "aligned") != "unaligned":
                aligned_word_ids.add(word_id)
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
            if cut_id in cut_ids:
                issues.append(
                    _issue(
                        ErrorCode.E_DUPLICATE_ID,
                        f"cuts[{len(cut_ids)}].id",
                        "cut ID is duplicated",
                    )
                )
            cut_ids.add(cut_id)
    gap_actions = edl.get("gap_actions", [])
    seen_action_gap_ids: set[str] = set()
    all_cut_ids = set(cut_ids)
    for index, action in enumerate(gap_actions):
        if not isinstance(action, Mapping):
            continue
        action_id = action.get("id")
        gap_id = action.get("gap_id")
        if isinstance(action_id, str):
            if action_id in all_cut_ids:
                issues.append(
                    _issue(
                        ErrorCode.E_DUPLICATE_ID, f"gap_actions[{index}].id", "cut ID is duplicated"
                    )
                )
            all_cut_ids.add(action_id)
        if isinstance(gap_id, str):
            if gap_id not in gap_ids:
                issues.append(
                    _issue(
                        ErrorCode.E_REF_GAP,
                        f"gap_actions[{index}].gap_id",
                        "gap action references a missing gap",
                    )
                )
            if gap_id in seen_action_gap_ids:
                issues.append(
                    _issue(
                        ErrorCode.E_DUPLICATE_ID,
                        f"gap_actions[{index}].gap_id",
                        "gap has more than one action",
                    )
                )
            seen_action_gap_ids.add(gap_id)

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
        if (
            from_index is not None
            and isinstance(from_word, str)
            and from_word not in aligned_word_ids
        ):
            issues.append(
                _issue(
                    ErrorCode.E_WORD_UNALIGNED,
                    f"cuts[{index}].remove.from_word",
                    "cut uses a word without aligned timing",
                )
            )
        if to_index is not None and isinstance(to_word, str) and to_word not in aligned_word_ids:
            issues.append(
                _issue(
                    ErrorCode.E_WORD_UNALIGNED,
                    f"cuts[{index}].remove.to_word",
                    "cut uses a word without aligned timing",
                )
            )
        if from_index is not None and to_index is not None:
            if from_index > to_index:
                issues.append(
                    _issue(ErrorCode.E_CUT_ORDER, f"cuts[{index}].remove", "cut range is reversed")
                )
            else:
                ranges.append((from_index, to_index, index))
                if any(
                    isinstance(row, Mapping)
                    and row.get("alignment_status", "aligned") == "unaligned"
                    for row in word_rows[from_index : to_index + 1]
                ):
                    issues.append(
                        _issue(
                            ErrorCode.E_WORD_UNALIGNED,
                            f"cuts[{index}].remove",
                            "cut range includes a word without aligned timing",
                        )
                    )

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
        elif isinstance(value, str) and value not in aligned_word_ids:
            issues.append(
                _issue(
                    ErrorCode.E_WORD_UNALIGNED, path, "reference uses a word without aligned timing"
                )
            )

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
                    aligned_word_ids,
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


def check_timeline(timeline: Mapping[str, Any]) -> list[ValidationIssue]:
    """Check unique timeline IDs and references within the synthetic linked A/V group."""
    issues: list[ValidationIssue] = []
    try:
        fps_text = timeline.get("fps")
        if isinstance(fps_text, str) and Fraction(fps_text) <= 0:
            issues.append(_issue(ErrorCode.E_WORD_TIME, "fps", "frame rate must be positive"))
    except (ValueError, ZeroDivisionError):
        issues.append(_issue(ErrorCode.E_SCHEMA, "fps", "frame rate is not a valid rational"))

    tracks = timeline.get("tracks", [])
    track_rows: dict[str, Mapping[str, Any]] = {}
    seen_track_slots: set[tuple[Any, Any]] = set()
    if isinstance(tracks, list):
        for index, track in enumerate(tracks):
            if not isinstance(track, Mapping):
                continue
            track_id = track.get("id")
            if not isinstance(track_id, str):
                continue
            if track_id in track_rows:
                issues.append(
                    _issue(
                        ErrorCode.E_DUPLICATE_ID, f"tracks[{index}].id", "track ID is duplicated"
                    )
                )
            track_rows[track_id] = track
            slot = (track.get("kind"), track.get("index"))
            if slot in seen_track_slots:
                issues.append(
                    _issue(
                        ErrorCode.E_DUPLICATE_ID, f"tracks[{index}]", "track index is duplicated"
                    )
                )
            seen_track_slots.add(slot)

    groups = timeline.get("groups", [])
    group_rows: dict[str, Mapping[str, Any]] = {}
    if isinstance(groups, list):
        for index, group in enumerate(groups):
            if not isinstance(group, Mapping):
                continue
            group_id = group.get("id")
            if not isinstance(group_id, str):
                continue
            if group_id in group_rows:
                issues.append(
                    _issue(
                        ErrorCode.E_DUPLICATE_ID, f"groups[{index}].id", "group ID is duplicated"
                    )
                )
            group_rows[group_id] = group

    events = timeline.get("events", [])
    event_rows: dict[str, Mapping[str, Any]] = {}
    event_kinds: list[str] = []
    if isinstance(events, list):
        for index, event in enumerate(events):
            if not isinstance(event, Mapping):
                continue
            path = f"events[{index}]"
            event_id = event.get("id")
            if not isinstance(event_id, str):
                continue
            if event_id in event_rows:
                issues.append(
                    _issue(ErrorCode.E_DUPLICATE_ID, f"{path}.id", "event ID is duplicated")
                )
            event_rows[event_id] = event
            track_id = event.get("track_id")
            track = track_rows.get(track_id) if isinstance(track_id, str) else None
            if track is None:
                issues.append(
                    _issue(
                        ErrorCode.E_REF_TRACK,
                        f"{path}.track_id",
                        "event references a missing track",
                    )
                )
            else:
                kind = track.get("kind")
                if isinstance(kind, str):
                    event_kinds.append(kind)
            group_id = event.get("group_id")
            if not isinstance(group_id, str) or group_id not in group_rows:
                issues.append(
                    _issue(
                        ErrorCode.E_REF_GROUP,
                        f"{path}.group_id",
                        "event references a missing group",
                    )
                )
            source_offset = event.get("source_offset_frames")
            length = event.get("length_frames")
            duration = timeline.get("duration_frames")
            if type(source_offset) is int and type(length) is int and type(duration) is int:
                if source_offset + length > duration:
                    issues.append(
                        _issue(
                            ErrorCode.E_REPORT_RANGE,
                            path,
                            "event source range exceeds timeline duration",
                        )
                    )

    if event_kinds.count("video") != 1 or event_kinds.count("audio") < 1:
        issues.append(
            _issue(
                ErrorCode.E_REPORT_CONSISTENCY,
                "events",
                "timeline requires one video event and at least one audio event",
            )
        )

    listed_events: list[str] = []
    for index, group in enumerate(groups if isinstance(groups, list) else []):
        if not isinstance(group, Mapping):
            continue
        members = group.get("event_ids", [])
        if not isinstance(members, list):
            continue
        for member_index, member in enumerate(members):
            path = f"groups[{index}].event_ids[{member_index}]"
            if not isinstance(member, str) or member not in event_rows:
                issues.append(
                    _issue(ErrorCode.E_REF_EVENT, path, "group references a missing event")
                )
            elif member in listed_events:
                issues.append(
                    _issue(ErrorCode.E_DUPLICATE_ID, path, "event belongs to multiple groups")
                )
            listed_events.append(member)
    if set(listed_events) != set(event_rows):
        issues.append(
            _issue(
                ErrorCode.E_REPORT_CONSISTENCY,
                "groups",
                "linked group membership does not cover all events",
            )
        )
    return issues


def check_compile_report(report: Mapping[str, Any]) -> list[ValidationIssue]:
    """Check frame totals, the displayed removal percentage, and snap IDs."""
    issues: list[ValidationIssue] = []
    source_frames = report.get("source_frames")
    removed_frames = report.get("removed_frames")
    removed_percent = report.get("removed_percent")
    if type(source_frames) is int and type(removed_frames) is int:
        if source_frames <= 0 or removed_frames < 0 or removed_frames > source_frames:
            issues.append(
                _issue(
                    ErrorCode.E_REPORT_RANGE,
                    "removed_frames",
                    "removed frames exceed the source range",
                )
            )
        elif isinstance(removed_percent, int | float) and not isinstance(removed_percent, bool):
            expected = removed_frames * 100 / source_frames
            if not math.isfinite(float(removed_percent)) or not math.isclose(
                float(removed_percent), expected, rel_tol=1e-7, abs_tol=0.00001
            ):
                issues.append(
                    _issue(
                        ErrorCode.E_REPORT_CONSISTENCY,
                        "removed_percent",
                        "percentage does not match frame totals",
                    )
                )

    seen_snap_ids: set[str] = set()
    for index, snap in enumerate(report.get("snaps", [])):
        if not isinstance(snap, Mapping):
            continue
        snap_id = snap.get("id")
        if isinstance(snap_id, str):
            if snap_id in seen_snap_ids:
                issues.append(
                    _issue(ErrorCode.E_DUPLICATE_ID, f"snaps[{index}].id", "snap ID is duplicated")
                )
            seen_snap_ids.add(snap_id)
    return issues


def check_verify_report(report: Mapping[str, Any]) -> list[ValidationIssue]:
    """Ensure overall pass state and machine-readable fixes agree with checks."""
    issues: list[ValidationIssue] = []
    checks = report.get("checks", [])
    passed_checks = [check for check in checks if isinstance(check, Mapping)]
    overall_passed = all(check.get("passed") is True for check in passed_checks)
    if report.get("passed") is not overall_passed:
        issues.append(
            _issue(
                ErrorCode.E_REPORT_CONSISTENCY,
                "passed",
                "overall result disagrees with check results",
            )
        )
    suggestions = report.get("fix_suggestions", [])
    for index, check in enumerate(passed_checks):
        if check.get("passed") is True:
            continue
        target_id = check.get("target_id") or check.get("id")
        if not any(
            isinstance(suggestion, Mapping) and suggestion.get("target_id") == target_id
            for suggestion in suggestions
        ):
            issues.append(
                _issue(
                    ErrorCode.E_REPORT_CONSISTENCY,
                    f"checks[{index}]",
                    "failed check has no fix suggestion",
                )
            )
    return issues


def check_run_manifest(manifest: Mapping[str, Any]) -> list[ValidationIssue]:
    """Check source immutability and the documented characters-based token estimate."""
    issues: list[ValidationIssue] = []
    integrity = manifest.get("source_integrity", {})
    if isinstance(integrity, Mapping):
        before = integrity.get("sha256_before")
        after = integrity.get("sha256_after")
        unchanged = integrity.get("unchanged")
        if isinstance(before, str) and isinstance(after, str) and isinstance(unchanged, bool):
            if unchanged != (before == after):
                issues.append(
                    _issue(
                        ErrorCode.E_MANIFEST_INTEGRITY,
                        "source_integrity",
                        "hash comparison disagrees with unchanged flag",
                    )
                )
    files = integrity.get("files", []) if isinstance(integrity, Mapping) else []
    seen_files: set[str] = set()
    if isinstance(files, list):
        for index, item in enumerate(files):
            if not isinstance(item, Mapping):
                continue
            file_id = item.get("id")
            if isinstance(file_id, str):
                if file_id in seen_files:
                    issues.append(
                        _issue(
                            ErrorCode.E_DUPLICATE_ID,
                            f"source_integrity.files[{index}].id",
                            "source integrity file ID is duplicated",
                        )
                    )
                seen_files.add(file_id)
            file_before = item.get("sha256_before")
            file_after = item.get("sha256_after")
            file_unchanged = item.get("unchanged")
            if (
                isinstance(file_before, str)
                and isinstance(file_after, str)
                and isinstance(file_unchanged, bool)
                and file_unchanged != (file_before == file_after)
            ):
                issues.append(
                    _issue(
                        ErrorCode.E_MANIFEST_INTEGRITY,
                        f"source_integrity.files[{index}]",
                        "file hash comparison disagrees with unchanged flag",
                    )
                )
    estimate = manifest.get("token_estimate", {})
    if isinstance(estimate, Mapping):
        characters = estimate.get("pack_characters")
        tokens = estimate.get("estimated_tokens")
        if type(characters) is int and type(tokens) is int and tokens != (characters + 3) // 4:
            issues.append(
                _issue(
                    ErrorCode.E_REPORT_CONSISTENCY,
                    "token_estimate",
                    "token estimate does not match ceil(chars / 4)",
                )
            )
    seen_inputs: set[str] = set()
    for index, item in enumerate(manifest.get("inputs", [])):
        if not isinstance(item, Mapping):
            continue
        item_id = item.get("id")
        if isinstance(item_id, str):
            if item_id in seen_inputs:
                issues.append(
                    _issue(
                        ErrorCode.E_DUPLICATE_ID, f"inputs[{index}].id", "input ID is duplicated"
                    )
                )
            seen_inputs.add(item_id)
    return issues
