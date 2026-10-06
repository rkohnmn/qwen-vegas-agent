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
from orchestrator.cli import DryRunError, _load_settings, _workspace_path
from orchestrator.compiler import CompileConfig, compile_edl
from orchestrator.contracts import (
    check_edl_against,
    check_ops,
    check_timeline,
    check_words,
    validate,
)
from orchestrator.packer import build_pack
from orchestrator.planner import BaselinePlanner, RecordedPlanner
from orchestrator.timeline import build_timeline
from perception.asr import AsrResult, AsrWord, WhisperXConfig, WhisperXEngine
from perception.audio import extract_audio_stream, hash_media_file, read_pcm16_mono
from perception.gaps import GapThresholds
from perception.preflight import MediaToolError, probe_media
from perception.words import build_words_document


def _new_output(value: str | Path | None, label: str) -> Path:
    default = (
        Path("runs")
        / f"{label}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    output = _workspace_path(value or default, "output directory")
    output.mkdir(parents=True, exist_ok=False)
    return output


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
                "real_time_factor": round(duration_s / elapsed, 4) if elapsed else None,
                "vram_gb": None,
                "fallback_reason": result.fallback_reason,
            }
        )
        gap_sources.append((result, str(artifact.path)))
        max_segment = max((word.segment_index for word in result.words), default=-1)
        merged_words.extend(
            replace(word, segment_index=word.segment_index + segment_offset, track=f"audio_{index}")
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
        speaker_mode="single" if len(artifacts) == 1 else "multitrack",
        thresholds=thresholds,
        gap_sources=gap_sources,
    )
    if validate("words", words) or check_words(words):
        raise DryRunError("ASR output failed words contract validation")
    write_json(output / "words.json", words)
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
    if validate("edl", edl) or check_edl_against(edl, words, {"speakers": {}}, catalog):
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
) -> Path:
    """Validate inputs and write frame-resolved ops plus compile report."""
    try:
        words = json.loads(Path(words_path).read_text(encoding="utf-8"))
        timeline = json.loads(Path(timeline_path).read_text(encoding="utf-8"))
        edl = json.loads(Path(edl_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DryRunError("compile input could not be read") from None
    if not all(isinstance(item, dict) for item in (words, timeline, edl)):
        raise DryRunError("compile input has an invalid shape")
    if (
        validate("words", words)
        or check_words(words)
        or validate("timeline", timeline)
        or check_timeline(timeline)
    ):
        raise DryRunError("words or timeline input failed contract validation")
    catalog: dict[str, Any] = {
        "transitions": [],
        "video_fx": [],
        "audio_fx": [],
        "text_presets": [],
        "sfx": [],
    }
    if validate("edl", edl) or check_edl_against(edl, words, {"speakers": {}}, catalog, timeline):
        raise DryRunError("EDL input failed schema or referential validation")
    output = _new_output(output_root, "compile")
    settings = _load_settings()["compile"]
    config = CompileConfig(
        head_pad_ms=settings["head_pad_ms"],
        tail_pad_ms=settings["tail_pad_ms"],
        min_gap_after_cut_ms=settings["min_gap_after_cut_ms"],
        audio_crossfade_ms=settings["audio_crossfade_ms"],
        max_removed_percent=settings["max_removed_percent"],
        snap_zero_crossing=settings["snap_zero_crossing"],
    )
    audio_samples = None
    sample_rate = None
    if audio_path is not None:
        safe_audio_path = _workspace_path(audio_path, "audio analysis file")
        audio_samples, sample_rate = read_pcm16_mono(safe_audio_path)
    ops, report, _ = compile_edl(
        edl,
        words,
        timeline,
        job_id=output.name,
        working_copy_path=str(output / "working_copy_placeholder.veg"),
        config=config,
        audio_samples=audio_samples,
        sample_rate=sample_rate,
    )
    if validate("ops", ops) or check_ops(ops, output) or validate("compile_report", report):
        raise DryRunError("compiler output failed contract validation")
    write_json(output / "ops.json", ops)
    write_json(output / "compile_report.json", report)
    return output
