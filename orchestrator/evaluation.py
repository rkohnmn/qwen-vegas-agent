"""Offline synthetic baseline metrics and editable ground-truth templates."""

from __future__ import annotations

import json
import math
import tempfile
import time
import tracemalloc
import wave
from array import array
from fractions import Fraction
from pathlib import Path
from typing import Any

from perception.asr import AsrWord, FakeAsrEngine
from perception.gaps import GapThresholds
from perception.words import build_words_document

from .caption_renderers import SidecarOnlyRenderer, parse_ass, parse_srt
from .captions import CaptionConfig, build_captions
from .compiler import CompileConfig, FrameInterval, compile_edl, kept_intervals
from .contracts import check_captions, check_edl_against, check_timeline, hash_words, validate
from .packer import build_pack
from .planner import BaselinePlanner
from .verifier import verify_audio


def _write_synthetic_tones(
    output: Path, words: tuple[AsrWord, ...], *, duration_s: int = 4, sample_rate: int = 16000
) -> None:
    """Write tone bursts at fixture word boundaries with silence elsewhere."""
    values = array("h")
    for sample_index in range(duration_s * sample_rate):
        time_s = sample_index / sample_rate
        active = any(
            word.aligned
            and word.start is not None
            and word.end is not None
            and word.start <= time_s < word.end
            for word in words
        )
        value = round(9000 * math.sin(2 * math.pi * 220 * time_s)) if active else 0
        values.append(value)
    with wave.open(str(output), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(values.tobytes())


def _nearest_fraction(value: Fraction) -> int:
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def _render_synthetic_cut(
    source_path: Path,
    output_path: Path,
    fps: str,
    duration_frames: int,
    removed: list[FrameInterval],
    *,
    sample_rate: int = 16000,
    fade_ms: int = 20,
) -> tuple[int, ...]:
    """Render cut synthetic PCM with a small crossfade, using only the stdlib."""
    with wave.open(str(source_path), "rb") as audio:
        source = array("h")
        source.frombytes(audio.readframes(audio.getnframes()))
    rate = Fraction(fps)
    ranges = kept_intervals(duration_frames, removed)
    chunks = []
    for start_frame, end_frame in ranges:
        start_sample = _nearest_fraction(Fraction(start_frame * sample_rate, 1) / rate)
        end_sample = _nearest_fraction(Fraction(end_frame * sample_rate, 1) / rate)
        if end_sample > start_sample:
            chunks.append(source[start_sample:end_sample])
    if not chunks:
        raise ValueError("synthetic edit leaves no audio")
    result = array("h", chunks[0])
    joins: list[int] = []
    crossfade = max(0, round(sample_rate * fade_ms / 1000))
    for chunk in chunks[1:]:
        actual = min(crossfade, len(result) // 2, len(chunk) // 2)
        overlap_start = len(result) - actual
        joins.append(overlap_start + actual // 2)
        for offset in range(actual):
            weight = (offset + 1) / (actual + 1)
            mixed = result[overlap_start + offset] * (1 - weight) + chunk[offset] * weight
            result[overlap_start + offset] = max(-32768, min(32767, round(mixed)))
        result.extend(chunk[actual:])
    with wave.open(str(output_path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(result.tobytes())
    return tuple(joins)


def synthetic_case() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_hash = "sha256:" + "d" * 64
    repository = Path(__file__).resolve().parents[1]
    asr_fixture = repository / "tests" / "data" / "synthetic_speech.json"
    fake_result = FakeAsrEngine.from_fixture(asr_fixture).transcribe_aligned("synthetic-tone.wav")
    with tempfile.TemporaryDirectory(prefix="m1-synthetic-") as temporary_directory:
        source_wav = Path(temporary_directory) / "tone.wav"
        _write_synthetic_tones(source_wav, fake_result.words)
        words = build_words_document(
            fake_result,
            str(source_wav),
            source_hash,
            "30/1",
            speaker_mode="single",
            thresholds=GapThresholds(
                minimum_gap_ms=250,
                window_ms=10,
                noise_floor_multiplier=2.5,
                absolute_rms_floor=0.002,
                minimum_quiet_ms=40,
            ),
        )
    timeline: dict[str, Any] = {
        "schema_version": "1.0.0",
        "source_hash": source_hash,
        "fps": "30/1",
        "duration_frames": 120,
        "tracks": [
            {"id": "v0", "kind": "video", "index": 0},
            {"id": "a0", "kind": "audio", "index": 0},
        ],
        "groups": [{"id": "lg0", "event_ids": ["e0", "e1"]}],
        "events": [
            {
                "id": "e0",
                "track_id": "v0",
                "group_id": "lg0",
                "start_frame": 0,
                "source_offset_frames": 0,
                "length_frames": 120,
            },
            {
                "id": "e1",
                "track_id": "a0",
                "group_id": "lg0",
                "start_frame": 0,
                "source_offset_frames": 0,
                "length_frames": 120,
            },
        ],
    }
    truth_path = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "evals"
        / ("synthetic-tone-silence-v1.truth.json")
    )
    truth_document = json.loads(truth_path.read_text(encoding="utf-8"))
    truth_word_cuts: set[tuple[str, str]] = set()
    truth_gap_cuts: set[str] = set()
    truth_word_bounds: dict[tuple[str, str], tuple[float, float]] = {}
    truth_gap_bounds: dict[str, tuple[float, float]] = {}
    word_rows = words["words"]
    for expected in truth_document["expected_cuts"]:
        if "from_text" in expected:
            matching = [
                row
                for row in word_rows
                if str(row["text"]).casefold() == expected["from_text"].casefold()
            ]
            if matching:
                word_key = (matching[0]["id"], matching[-1]["id"])
                truth_word_cuts.add(word_key)
                truth_word_bounds[word_key] = (
                    matching[0]["start"],
                    matching[-1]["end"],
                )
        else:
            matching_gaps = [
                gap
                for gap in words["gaps"]
                if abs(gap["start"] - expected["approximate_start_s"]) < 0.05
                and abs(gap["end"] - expected["approximate_end_s"]) < 0.05
            ]
            if matching_gaps:
                gap_id = matching_gaps[0]["id"]
                truth_gap_cuts.add(gap_id)
                truth_gap_bounds[gap_id] = (
                    expected["approximate_start_s"],
                    expected["approximate_end_s"],
                )
    truth = {
        "word_cuts": truth_word_cuts,
        "gap_cuts": truth_gap_cuts,
        "word_bounds": truth_word_bounds,
        "gap_bounds": truth_gap_bounds,
    }
    return words, timeline, truth


def run_speaker_synthetic_eval() -> dict[str, Any]:
    """Measure deterministic speaker logic on tiny labeled vectors and word rows."""
    from perception.speakers import (
        DiarizationTurn,
        apply_bleed_confidence,
        attribute_multitrack_words,
        attribute_words_from_turns,
        match_embedding,
    )

    started = time.perf_counter()
    tracemalloc.start()
    try:
        multitrack_words: list[dict[str, Any]] = [
            {"id": "w1", "track": "audio_0", "speaker": None, "speaker_conf": 0.0},
            {"id": "w2", "track": "audio_1", "speaker": None, "speaker_conf": 0.0},
        ]
        attribute_multitrack_words(multitrack_words, {"audio_0": "host", "audio_1": "guest"})
        multitrack_correct = sum(
            word["speaker"] == expected
            for word, expected in zip(multitrack_words, ("host", "guest"), strict=True)
        )
        bleed_words: list[dict[str, Any]] = [
            {
                "id": "w3",
                "text": "hello",
                "start": 1.0,
                "end": 1.4,
                "track": "audio_0",
                "speaker_conf": 1.0,
            },
            {
                "id": "w4",
                "text": "hello",
                "start": 1.0,
                "end": 1.4,
                "track": "audio_1",
                "speaker_conf": 1.0,
            },
        ]
        bleed_reasons = apply_bleed_confidence(
            bleed_words,
            {"w3": {"audio_0": 10.0}, "w4": {"audio_1": 100.0}},
        )
        diarized_words: list[dict[str, Any]] = [
            {"id": "w5", "start": 0.0, "end": 1.0, "speaker": None, "speaker_conf": 0.0}
        ]
        attribute_words_from_turns(
            diarized_words,
            (DiarizationTurn("cluster_a", 0.0, 1.0), DiarizationTurn("cluster_b", 0.5, 1.0)),
            {"cluster_a": "host", "cluster_b": "guest"},
        )
        unknown_key, _score = match_embedding((0.0, 1.0), {"host": (1.0, 0.0)}, threshold=0.65)
        _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    elapsed = time.perf_counter() - started
    synthetic_duration_s = 10.0
    return {
        "dataset": "synthetic-speaker-v1",
        "device": "CPU",
        "model": "fixture-vectors; no checkpoint loaded",
        "multitrack": {
            "correct": multitrack_correct,
            "total": 2,
            "accuracy": multitrack_correct / 2,
        },
        "diarized": {
            "correct": int(diarized_words[0]["speaker"] == "host"),
            "total": 1,
            "accuracy": float(diarized_words[0]["speaker"] == "host"),
        },
        "overlap": {
            "correct": int(diarized_words[0]["overlap"] is True),
            "total": 1,
            "accuracy": float(diarized_words[0]["overlap"] is True),
        },
        "bleed": {
            "flagged": int("w3" in bleed_reasons),
            "candidates": 1,
            "flag_rate": float("w3" in bleed_reasons),
        },
        "unknown_detection": {
            "detected": int(unknown_key is None),
            "clusters": 1,
            "rate": float(unknown_key is None),
        },
        "wall_clock_ms": round(elapsed * 1000, 3),
        "wall_clock_per_media_minute_s": round(elapsed / (synthetic_duration_s / 60), 6),
        "peak_traced_memory_bytes": peak_bytes,
        "scope_note": "Synthetic algorithm plumbing only; not a real-speech or model benchmark.",
    }


def run_synthetic_caption_eval() -> dict[str, Any]:
    """Measure a synthetic 300-caption layout/export and verify both sidecar round trips."""
    fps = "25/1"
    rows: list[dict[str, Any]] = []
    cursor = 0
    for index in range(1, 301):
        start_frame = cursor
        end_frame = start_frame + 10
        rows.append(
            {
                "id": f"w{index}",
                "text": f"word{index}",
                "start": start_frame / 25,
                "end": end_frame / 25,
                "speaker": "host" if index % 2 else "guest",
                "speaker_conf": 0.98,
                "alignment_status": "aligned",
            }
        )
        cursor += 25
    words: dict[str, Any] = {"fps": fps, "words": rows}
    edl: dict[str, Any] = {
        "subtitles": {"style": None, "emphasis": [], "break_hints": [], "omit_ranges": []}
    }
    timeline: dict[str, Any] = {"fps": fps, "duration_frames": cursor + 10}
    speakers: dict[str, Any] = {
        "schema_version": "1.1.0",
        "speakers": {
            "host": {"display": "Host", "color": "#4FC3F7"},
            "guest": {"display": "Guest", "color": "#FFB74D"},
        },
        "unknown_palette": ["#BDBDBD", "#CE93D8"],
    }
    config = CaptionConfig(max_cps=100, min_duration_ms=1, hold_ms=0)
    started = time.perf_counter()
    document, report = build_captions(
        words, edl, timeline, [], config=config, speakers_document=speakers
    )
    layout_ms = (time.perf_counter() - started) * 1000
    if validate("captions", document) or check_captions(document, words):
        raise ValueError("synthetic caption evaluation produced an invalid document")
    with tempfile.TemporaryDirectory(prefix="caption-eval-", dir=Path.cwd()) as temporary:
        started = time.perf_counter()
        json_path, srt_path, ass_path, _report_path = SidecarOnlyRenderer().write_sidecars(
            temporary, document, report, speakers, config
        )
        export_ms = (time.perf_counter() - started) * 1000
        if json_path.stat().st_size == 0:
            raise ValueError("synthetic caption JSON export is empty")
        if parse_srt(srt_path.read_text(encoding="utf-8"), fps) != [
            {
                "start_frame": row["start_frame"],
                "end_frame": row["end_frame"],
                "text": row["text"],
            }
            for row in document["captions"]
        ]:
            raise ValueError("synthetic SRT parse-back did not match caption frames")
        if parse_ass(ass_path.read_text(encoding="utf-8"), fps) != [
            {
                "start_frame": row["start_frame"],
                "end_frame": row["end_frame"],
                "text": row["text"],
            }
            for row in document["captions"]
        ]:
            raise ValueError("synthetic ASS parse-back did not match caption frames")
    return {
        "input_words": len(rows),
        "captions": len(document["captions"]),
        "layout_wall_ms": round(layout_ms, 3),
        "sidecar_export_wall_ms": round(export_ms, 3),
        "srt_ass_round_trip": "passed",
        "speaker_colors": "resolved from synthetic speakers map",
        "scope_note": "Synthetic local measurement; not Vegas event or render performance.",
    }


def run_synthetic_eval() -> dict[str, Any]:
    """Measure deterministic baseline selection against a tiny labeled synthetic case."""
    started = time.perf_counter()
    words, timeline, truth = synthetic_case()
    if validate("words", words) or validate("timeline", timeline) or check_timeline(timeline):
        raise ValueError("synthetic eval fixture violates a contract")
    pack = build_pack(words)
    edl = BaselinePlanner(minimum_gap_ms=650).plan(pack.text, words, {})
    catalog: dict[str, list[dict[str, Any]]] = {
        "transitions": [],
        "video_fx": [],
        "audio_fx": [],
        "text_presets": [],
        "sfx": [],
    }
    if validate("edl", edl) or check_edl_against(edl, words, {"speakers": {}}, catalog, timeline):
        raise ValueError("synthetic baseline EDL failed validation")
    predicted_words = {
        (item["remove"]["from_word"], item["remove"]["to_word"]) for item in edl["cuts"]
    }
    predicted_gaps = {item["gap_id"] for item in edl["gap_actions"]}
    expected = truth["word_cuts"] | {("gap", gap_id) for gap_id in truth["gap_cuts"]}
    predicted = predicted_words | {("gap", gap_id) for gap_id in predicted_gaps}
    true_positive = len(expected & predicted)
    precision = true_positive / len(predicted) if predicted else 1.0
    recall = true_positive / len(expected) if expected else 1.0
    ops, report, intervals = compile_edl(
        edl,
        words,
        timeline,
        job_id="synthetic_eval",
        working_copy_path="runs/synthetic_eval/working_copy.veg",
        config=CompileConfig(),
    )
    truth_key_by_item_id = {
        item["id"]: (item["remove"]["from_word"], item["remove"]["to_word"]) for item in edl["cuts"]
    }
    truth_key_by_item_id.update(
        {item["id"]: ("gap", item["gap_id"]) for item in edl["gap_actions"]}
    )
    applied_item_ids = {
        item_id
        for operation in ops["operations"]
        if operation.get("op") == "delete_range"
        for item_id in operation.get("item_ids", [])
    }
    applied_predicted = {
        truth_key_by_item_id[item_id]
        for item_id in applied_item_ids
        if item_id in truth_key_by_item_id
    }
    applied_true_positive = len(expected & applied_predicted)
    applied_precision = applied_true_positive / len(applied_predicted) if applied_predicted else 1.0
    applied_recall = applied_true_positive / len(expected) if expected else 1.0
    proposed_count = len(truth_key_by_item_id)
    not_applied_count = sum(
        outcome["status"] in {"rejected", "adjusted"} for outcome in report["item_outcomes"]
    )
    not_applied_percent = not_applied_count * 100 / proposed_count if proposed_count else 0.0
    partial_word_cuts = 0
    for interval in intervals:
        for row in words["words"]:
            start = int(row["start"] * 30)
            end = int(row["end"] * 30 + 0.999999)
            intersects = interval.start < end and interval.end > start
            fully_removed = interval.start <= start and interval.end >= end
            if intersects and not fully_removed:
                partial_word_cuts += 1
    word_by_id = {row["id"]: row for row in words["words"]}
    gap_by_id = {gap["id"]: gap for gap in words["gaps"]}
    offset_errors_ms: list[float] = []
    for item in edl["cuts"]:
        key = (item["remove"]["from_word"], item["remove"]["to_word"])
        expected_bounds = truth["word_bounds"].get(key)
        if expected_bounds is not None:
            first = word_by_id[key[0]]
            last = word_by_id[key[1]]
            offset_errors_ms.extend(
                [
                    abs(first["start"] - expected_bounds[0]) * 1000,
                    abs(last["end"] - expected_bounds[1]) * 1000,
                ]
            )
    for item in edl["gap_actions"]:
        gap_id = item["gap_id"]
        expected_bounds = truth["gap_bounds"].get(gap_id)
        if expected_bounds is not None:
            gap = gap_by_id[gap_id]
            offset_errors_ms.extend(
                [
                    abs(gap["start"] - expected_bounds[0]) * 1000,
                    abs(gap["end"] - expected_bounds[1]) * 1000,
                ]
            )

    repository = Path(__file__).resolve().parents[1]
    asr_fixture = repository / "tests" / "data" / "synthetic_speech.json"
    fake_result = FakeAsrEngine.from_fixture(asr_fixture).transcribe_aligned("synthetic-tone.wav")
    with tempfile.TemporaryDirectory(prefix="m1-synthetic-render-") as temporary_directory:
        source_wav = Path(temporary_directory) / "source.wav"
        output_wav = Path(temporary_directory) / "cut.wav"
        _write_synthetic_tones(source_wav, fake_result.words)
        join_samples = _render_synthetic_cut(
            source_wav,
            output_wav,
            timeline["fps"],
            timeline["duration_frames"],
            intervals,
        )
        verification = verify_audio(
            output_wav,
            join_samples,
            removed_percent=report["removed_percent"],
            max_removed_percent=35.0,
            words=words,
            fps=timeline["fps"],
            removed=intervals,
            min_interword_gap_ms=120,
            max_interword_gap_ms=1800,
        )
    click_checks = [
        check for check in verification["checks"] if check["name"] == "click_discontinuity"
    ]
    click_rate = sum(not check["passed"] for check in click_checks) / max(1, len(click_checks))
    offset_errors_ms.sort()
    mean_offset = sum(offset_errors_ms) / max(1, len(offset_errors_ms))
    max_offset = max(offset_errors_ms, default=0.0)
    median_offset = (
        (
            offset_errors_ms[(len(offset_errors_ms) - 1) // 2]
            + offset_errors_ms[len(offset_errors_ms) // 2]
        )
        / 2
        if offset_errors_ms
        else 0.0
    )
    elapsed = time.perf_counter() - started
    duration_minutes = float(
        Fraction(timeline["duration_frames"], 1) / Fraction(timeline["fps"]) / 60
    )
    failed_verification_checks = [
        check["id"] for check in verification["checks"] if not check["passed"]
    ]
    return {
        "dataset": "synthetic-tone-silence-v1",
        "clips": 1,
        "prompt_version": "baseline-1",
        "schema_versions": {
            "words": "2.1.0",
            "edl": "2.0.0",
            "ops": "1.1.0",
            "compile_report": "2.1.0",
        },
        "cut_precision": round(precision, 4),
        "cut_recall": round(recall, 4),
        "applied_precision": round(applied_precision, 4),
        "applied_recall": round(applied_recall, 4),
        "proposed_rejected_or_adjusted_count": not_applied_count,
        "proposed_rejected_or_adjusted_percent": round(not_applied_percent, 4),
        "cut_offset_error_ms": {
            "mean": round(mean_offset, 3),
            "median": round(median_offset, 3),
            "max": round(max_offset, 3),
            "basis": "resolved planned word/gap anchors",
        },
        "clipped_word_rate": partial_word_cuts / max(1, len(intervals)),
        "click_rate": round(click_rate, 4),
        "verifier_passed": verification["passed"],
        "failed_verification_checks": failed_verification_checks,
        "removed_percent": report["removed_percent"],
        "wall_clock_ms": round(elapsed * 1000, 3),
        "wall_clock_per_minute_s": round(elapsed / duration_minutes, 4),
        "estimated_tokens": pack.estimated_tokens,
        "compile_rejections": len(report["rejected_items"]),
        "planner_retries": 0,
        "speaker_attribution": run_speaker_synthetic_eval(),
        "caption_sidecars": run_synthetic_caption_eval(),
        "scope_note": "Synthetic smoke check only; not a real-clip quality estimate.",
    }


def truth_template(words: dict[str, Any]) -> dict[str, Any]:
    """Return an editable ID-based truth skeleton derived from an aligned transcript."""
    return {
        "schema_version": "1.0.0",
        "source_hash": words["source_hash"],
        "words_hash": hash_words(words),
        "word_index": [
            {
                "id": row["id"],
                "text": row["text"],
                "start": row.get("start"),
                "end": row.get("end"),
                "alignment_status": row.get("alignment_status", "aligned"),
            }
            for row in words.get("words", [])
        ],
        "expected_cuts": [],
        "speaker_labels": [],
        "notes": "",
    }
