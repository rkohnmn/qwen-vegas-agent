"""Offline dry-run orchestration; never launches Vegas or contacts remote hosts."""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestrator.artifacts import write_cmx_edl, write_json, write_markers, write_review
from orchestrator.childenv import safe_child_environment
from orchestrator.compiler import CompileConfig, compile_edl
from orchestrator.contracts import (
    check_edl_against,
    check_ops,
    check_run_manifest,
    check_timeline,
    validate,
)
from orchestrator.metrics import real_time_factor
from orchestrator.packer import build_pack
from orchestrator.planner import (
    BaselinePlanner,
    EndpointUnreachable,
    Planner,
    PlannerError,
    RecordedPlanner,
)
from orchestrator.renderer import render_cut_audio
from orchestrator.timeline import build_timeline
from orchestrator.verifier import verify_audio
from perception.asr import AsrResult, AsrWord, WhisperXConfig, WhisperXEngine
from perception.audio import (
    AudioExtractionError,
    extract_audio_stream,
    hash_media_file,
    mix_normalized_audio,
    read_pcm16_mono,
)
from perception.gaps import GapThresholds
from perception.preflight import MediaToolError, probe_media
from perception.words import build_words_document


class DryRunError(RuntimeError):
    """Safe, typed local pipeline failure."""


def _load_settings() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    config_path = root / "config.json"
    if not config_path.is_file():
        config_path = root / "config.example.json"
    try:
        settings = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise DryRunError("local configuration could not be read") from None
    if not isinstance(settings, dict) or validate("config", settings):
        raise DryRunError("local configuration failed schema validation")
    return settings


def _workspace_path(value: str | Path, label: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    path = Path(value)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_relative_to(root):
        raise DryRunError(f"{label} must stay within the repository")
    return resolved


def _peak_vram_gb(device: str) -> float | None:
    if device != "cuda":
        return None
    try:
        torch = importlib.import_module("torch")
        return round(float(torch.cuda.max_memory_allocated()) / (1024**3), 3)
    except (ImportError, AttributeError, RuntimeError, TypeError):
        return None


def _tool_version(executable: str) -> str:
    resolved = shutil.which(executable)
    if resolved is None:
        return "unavailable"
    try:
        result = subprocess.run(
            [resolved, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            shell=False,
            env=safe_child_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    if result.returncode:
        return "unavailable"
    return result.stdout.splitlines()[0][:160] if result.stdout.splitlines() else "available"


def _status_manifest(
    *,
    job_id: str,
    source_hash_before: str,
    source_hash_after: str,
    status: str,
    code: str | None,
    message: str,
    stage_name: str,
    stage_wall_ms: int,
    pack_characters: int = 0,
    estimated_tokens: int = 0,
    asr_model: str = "not-run",
    align_model: str = "not-run",
) -> dict[str, Any]:
    return {
        "schema_version": "1.1.0",
        "job_id": job_id,
        "inputs": [{"id": "source_0", "sha256": source_hash_before.removeprefix("sha256:")}],
        "schemas": {"timeline": "1.0.0", "words": "2.0.0", "edl": "1.2.0", "ops": "1.1.0"},
        "tools": {
            "python": sys.version.split()[0],
            "ffmpeg": _tool_version("ffmpeg"),
            "ffprobe": _tool_version("ffprobe"),
            "asr_engine": "whisperx",
            "asr_model": asr_model,
            "align_model": align_model,
        },
        "stages": [
            {
                "name": stage_name,
                "wall_clock_ms": stage_wall_ms,
                "outcome": status,
                **({"error_code": code} if code else {}),
            }
        ],
        "token_estimate": {
            "pack_characters": pack_characters,
            "estimated_tokens": estimated_tokens,
            "method": "ceil_chars_div_4",
        },
        "source_integrity": {
            "sha256_before": source_hash_before,
            "sha256_after": source_hash_after,
            "unchanged": source_hash_before == source_hash_after,
        },
        "outcome": {"status": status, "code": code, "message": message},
    }


def run_dry_run(
    video_path: str | Path,
    *,
    max_seconds: int = 120,
    planner_name: str = "baseline",
    recorded_edl: str | Path | None = None,
    output_root: str | Path = "runs",
    cache_root: str | Path | None = None,
    llm_endpoint: str | None = None,
    llm_model: str = "qwen",
) -> Path:
    """Run available M1 stages in a disposable run/cache directory."""
    source = Path(video_path)
    if max_seconds < 1 or max_seconds > 36000:
        raise DryRunError("maximum duration is outside the supported range")
    if planner_name == "llm":
        raise EndpointUnreachable(
            "LLM requests are disabled in M1; the client is tested with loopback fakes only"
        )
    if planner_name == "recorded" and recorded_edl is None:
        raise PlannerError("recorded planner requires an EDL fixture")
    if planner_name not in {"baseline", "recorded"}:
        raise PlannerError("planner must be baseline or recorded in M1")
    settings = _load_settings()
    source_output_root = _workspace_path(output_root, "run output")
    source_cache_root = _workspace_path(cache_root or settings["paths"]["cache"], "cache")
    try:
        source_hash_before = hash_media_file(source)
    except AudioExtractionError:
        raise DryRunError("selected source media could not be read") from None
    job_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    root = source_output_root / job_id
    root.mkdir(parents=True, exist_ok=False)
    stage_start = time.perf_counter()
    stage_timings: list[dict[str, Any]] = []
    preflight_started = time.perf_counter()
    try:
        probe = probe_media(source)
    except MediaToolError as error:
        source_hash_after = hash_media_file(source)
        manifest = _status_manifest(
            job_id=job_id,
            source_hash_before=source_hash_before,
            source_hash_after=source_hash_after,
            status="blocked",
            code="E_MEDIA_TOOL",
            message=str(error),
            stage_name="preflight",
            stage_wall_ms=round((time.perf_counter() - stage_start) * 1000),
        )
        write_json(root / "run_manifest.json", manifest)
        raise DryRunError(str(error)) from None
    timeline = build_timeline(probe, source_hash_before, max_seconds=max_seconds)
    timeline_issues = [*validate("timeline", timeline), *check_timeline(timeline)]
    if timeline_issues:
        raise DryRunError("generated timeline failed contract validation")
    write_json(root / "timeline.json", timeline)
    stage_timings.append(
        {
            "name": "preflight",
            "wall_clock_ms": round((time.perf_counter() - preflight_started) * 1000),
            "outcome": "complete",
        }
    )

    audio_started = time.perf_counter()
    artifacts = [
        extract_audio_stream(
            source,
            stream.index,
            source_cache_root,
            duration_limit_s=max_seconds,
        )
        for stream in probe.audio_streams
    ]
    asr_settings = settings["asr"]
    engine = WhisperXEngine(
        WhisperXConfig(
            model=asr_settings["model"],
            device=asr_settings["device"],
            compute_type=asr_settings["compute_type"],
            language=asr_settings["language"],
            model_cache_dir=source_cache_root / "asr_models",
        )
    )
    stage_timings.append(
        {
            "name": "audio_extract",
            "wall_clock_ms": round((time.perf_counter() - audio_started) * 1000),
            "outcome": "complete",
        }
    )
    per_stream: list[AsrResult] = []
    merged_words: list[AsrWord] = []
    gap_sources: list[tuple[AsrResult, str]] = []
    segment_offset = 0
    asr_start = time.perf_counter()
    asr_measurements: list[dict[str, Any]] = []
    source_duration_s = (
        timeline["duration_frames"]
        * int(timeline["fps"].split("/")[1])
        / int(timeline["fps"].split("/")[0])
    )
    for index, artifact in enumerate(artifacts):
        stream_start = time.perf_counter()
        result = engine.transcribe_aligned(artifact.path)
        stream_elapsed = time.perf_counter() - stream_start
        per_stream.append(result)
        asr_measurements.append(
            {
                "stream_index": artifact.stream_index,
                "model": result.model,
                "align_model": result.align_model,
                "device": result.device,
                "compute_type": result.compute_type,
                "wall_clock_s": round(stream_elapsed, 3),
                "real_time_factor": real_time_factor(stream_elapsed, source_duration_s),
                "vram_gb": _peak_vram_gb(result.device),
                "fallback_reason": result.fallback_reason,
            }
        )
        gap_sources.append((result, str(artifact.path)))
        max_segment = max((word.segment_index for word in result.words), default=-1)
        merged_words.extend(
            replace(
                word,
                segment_index=word.segment_index + segment_offset,
                track=f"audio_{index}",
            )
            for word in result.words
        )
        segment_offset += max_segment + 1
    stage_timings.append(
        {
            "name": "asr",
            "wall_clock_ms": round((time.perf_counter() - asr_start) * 1000),
            "outcome": "complete",
        }
    )
    words_started = time.perf_counter()
    merged_words.sort(
        key=lambda word: (
            word.start is None,
            word.start if word.start is not None else float("inf"),
        )
    )
    primary = per_stream[0]
    merged_result = replace(primary, words=tuple(merged_words))
    gap_settings = settings["perception"]
    gap_limits = GapThresholds(
        minimum_gap_ms=gap_settings["gap_minimum_ms"],
        window_ms=gap_settings["gap_window_ms"],
        noise_floor_multiplier=gap_settings["gap_noise_floor_multiplier"],
        absolute_rms_floor=gap_settings["gap_absolute_rms_floor"],
        minimum_quiet_ms=gap_settings["gap_minimum_quiet_ms"],
    )
    words_doc = build_words_document(
        merged_result,
        str(artifacts[0].path),
        source_hash_before,
        timeline["fps"],
        speaker_mode="single" if len(artifacts) == 1 else "multitrack",
        thresholds=gap_limits,
        gap_sources=gap_sources,
    )
    from orchestrator.contracts import check_words

    words_issues = [*validate("words", words_doc), *check_words(words_doc)]
    if words_issues:
        raise DryRunError("ASR output failed words contract validation")
    write_json(root / "words.json", words_doc)
    write_json(
        root / "asr_benchmark.json",
        {
            "schema_version": "1.0.0",
            "clip_duration_s": round(source_duration_s, 3),
            "streams": asr_measurements,
        },
    )
    stage_timings.append(
        {
            "name": "transcript",
            "wall_clock_ms": round((time.perf_counter() - words_started) * 1000),
            "outcome": "complete",
        }
    )
    pack_started = time.perf_counter()
    pack = build_pack(words_doc)
    (root / "pack.txt").write_text(pack.text, encoding="utf-8")
    stage_timings.append(
        {
            "name": "pack",
            "wall_clock_ms": round((time.perf_counter() - pack_started) * 1000),
            "outcome": "complete",
        }
    )

    catalog: dict[str, Any] = {
        "transitions": [],
        "video_fx": [],
        "audio_fx": [],
        "text_presets": [],
        "sfx": [],
    }
    speakers: dict[str, Any] = {"speakers": {}}
    planner_started = time.perf_counter()
    planner: Planner
    if planner_name == "baseline":
        planner = BaselinePlanner()
    elif planner_name == "recorded" and recorded_edl is not None:
        planner = RecordedPlanner.from_file(recorded_edl)
    else:
        raise PlannerError("planner must be baseline, recorded with a fixture, or loopback llm")
    edl = planner.plan(pack.text, words_doc, catalog)
    edl_issues = [
        *validate("edl", edl),
        *check_edl_against(edl, words_doc, speakers, catalog, timeline),
    ]
    if edl_issues:
        raise DryRunError("planner output failed EDL schema or referential validation")
    write_json(root / "edl.json", edl)
    stage_timings.append(
        {
            "name": "plan",
            "wall_clock_ms": round((time.perf_counter() - planner_started) * 1000),
            "outcome": "complete",
        }
    )

    compile_settings = settings["compile"]
    audio_mix_started = time.perf_counter()
    mixed_audio = mix_normalized_audio(
        [artifact.path for artifact in artifacts],
        root / "reference_mix.wav",
    )
    audio_samples, audio_sample_rate = (
        read_pcm16_mono(mixed_audio) if compile_settings["snap_zero_crossing"] else (None, None)
    )
    stage_timings.append(
        {
            "name": "audio_mix",
            "wall_clock_ms": round((time.perf_counter() - audio_mix_started) * 1000),
            "outcome": "complete",
        }
    )
    compile_config = CompileConfig(
        head_pad_ms=compile_settings["head_pad_ms"],
        tail_pad_ms=compile_settings["tail_pad_ms"],
        min_gap_after_cut_ms=compile_settings["min_gap_after_cut_ms"],
        audio_crossfade_ms=compile_settings["audio_crossfade_ms"],
        max_removed_percent=compile_settings["max_removed_percent"],
        snap_zero_crossing=compile_settings["snap_zero_crossing"],
    )
    working_path = str((root / "working_copy_placeholder.veg").resolve())
    compile_started = time.perf_counter()
    ops, compile_report, removed = compile_edl(
        edl,
        words_doc,
        timeline,
        job_id=job_id,
        working_copy_path=working_path,
        config=compile_config,
        audio_samples=audio_samples,
        sample_rate=audio_sample_rate,
    )
    ops_issues = [*validate("ops", ops), *check_ops(ops, root)]
    report_issues = validate("compile_report", compile_report)
    if ops_issues or report_issues:
        raise DryRunError("compiler output failed contract validation")
    write_json(root / "ops.json", ops)
    write_json(root / "compile_report.json", compile_report)
    stage_timings.append(
        {
            "name": "compile",
            "wall_clock_ms": round((time.perf_counter() - compile_started) * 1000),
            "outcome": "complete",
        }
    )
    artifacts_started = time.perf_counter()
    write_markers(
        root / "markers.csv",
        ops["operations"],
        timeline["fps"],
        decisions=[*edl.get("cuts", []), *edl.get("gap_actions", [])],
    )
    write_cmx_edl(root / "cuts.edl", timeline["fps"], timeline["duration_frames"], removed)
    write_review(root / "review.md", edl, words_doc, compile_report)
    stage_timings.append(
        {
            "name": "review_artifacts",
            "wall_clock_ms": round((time.perf_counter() - artifacts_started) * 1000),
            "outcome": "complete",
        }
    )

    render_started = time.perf_counter()
    rendered = render_cut_audio(
        "ffmpeg",
        mixed_audio,
        root / "cut_audio.wav",
        timeline["fps"],
        timeline["duration_frames"],
        removed,
        fade_ms=compile_config.audio_crossfade_ms,
    )
    stage_timings.append(
        {
            "name": "render",
            "wall_clock_ms": round((time.perf_counter() - render_started) * 1000),
            "outcome": "complete",
        }
    )
    verify_started = time.perf_counter()
    verify_report = verify_audio(
        rendered.output,
        rendered.join_samples,
        removed_percent=compile_report["removed_percent"],
        max_removed_percent=compile_config.max_removed_percent,
        words=words_doc,
        fps=timeline["fps"],
        removed=removed,
        min_interword_gap_ms=compile_settings["min_gap_after_cut_ms"],
        max_interword_gap_ms=compile_settings["max_gap_after_cut_ms"],
    )
    from orchestrator.contracts import check_verify_report

    verify_issues = [*validate("verify_report", verify_report), *check_verify_report(verify_report)]
    if verify_issues:
        raise DryRunError("verifier output failed contract validation")
    write_json(root / "verify_report.json", verify_report)
    stage_timings.append(
        {
            "name": "verify",
            "wall_clock_ms": round((time.perf_counter() - verify_started) * 1000),
            "outcome": "complete",
        }
    )

    source_hash_after = hash_media_file(source)
    source_unchanged = source_hash_before == source_hash_after
    verification_passed = verify_report["passed"]
    run_passed = source_unchanged and verification_passed
    manifest_code = (
        None if run_passed else "E_SOURCE_CHANGED" if not source_unchanged else "E_VERIFY"
    )
    manifest = _status_manifest(
        job_id=job_id,
        source_hash_before=source_hash_before,
        source_hash_after=source_hash_after,
        status="complete" if run_passed else "failed",
        code=manifest_code,
        message=(
            "offline dry-run completed"
            if run_passed
            else "source integrity check failed"
            if not source_unchanged
            else "verification checks did not pass"
        ),
        stage_name="pipeline",
        stage_wall_ms=round((time.perf_counter() - stage_start) * 1000),
        pack_characters=pack.characters,
        estimated_tokens=pack.estimated_tokens,
        asr_model=primary.model,
        align_model=primary.align_model,
    )
    stage_timings.append(
        {
            "name": "pipeline",
            "wall_clock_ms": round((time.perf_counter() - stage_start) * 1000),
            "outcome": manifest["outcome"]["status"],
            **({"error_code": manifest_code} if manifest_code else {}),
        }
    )
    manifest["stages"] = stage_timings
    manifest_issues = [
        *validate("run_manifest", manifest),
        *check_run_manifest(manifest),
    ]
    if manifest_issues:
        raise DryRunError("run manifest failed contract validation")
    write_json(root / "run_manifest.json", manifest)
    if not source_unchanged:
        raise DryRunError("source integrity check failed")
    if not verification_passed:
        raise DryRunError("verification report contains failed checks")
    return root
