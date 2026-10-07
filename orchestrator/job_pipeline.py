"""Resumable, offline-first job orchestration around validated artifacts.

Vegas work remains disabled until matching human probes have E0 evidence.
The runner accepts prior timeline/word artifacts so its state machine can be
exercised with deterministic fixtures and fake adapters.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
import uuid
import wave
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from orchestrator.artifacts import write_cmx_edl, write_json, write_markers, write_review
from orchestrator.compiler import CompileConfig, FrameInterval, compile_edl
from orchestrator.contracts import (
    check_edl_against,
    check_ops,
    check_run_manifest,
    check_timeline,
    check_words,
    validate,
)
from orchestrator.packer import build_pack
from orchestrator.planner import BaselinePlanner, Planner, PlannerError
from orchestrator.renderer import RenderError, render_cut_audio
from orchestrator.verifier import verify_audio


class JobStageFailure(RuntimeError):
    """A stage failure with a stable code and a safe, path-free message."""

    def __init__(self, stage: str, code: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.message = message


class JobPaused(RuntimeError):
    """Raised internally after a requested checkpoint has been persisted."""


class ExecutorDisabledError(RuntimeError):
    """The real Vegas adapter is intentionally unavailable pending E0 probes."""


class JobExecutor(Protocol):
    """Adapter boundary for a validated operation batch."""

    adapter_name: str

    def execute(
        self, operations: dict[str, Any], working_copy: Path, working_dir: Path
    ) -> dict[str, Any]: ...


class AudioRenderer(Protocol):
    """Adapter boundary for rendering an audio preview from a copied project."""

    adapter_name: str

    def render(
        self,
        *,
        audio_path: Path,
        output_path: Path,
        fps: str,
        duration_frames: int,
        removed: Sequence[FrameInterval],
        fade_ms: int,
    ) -> tuple[int, ...]: ...


@dataclass(frozen=True, slots=True)
class JobOptions:
    mode: str = "dry-run"
    max_fix_iterations: int = 2
    initial_crossfade_ms: int = 20
    max_crossfade_ms: int = 80
    stop_after_stage: str | None = None


class DisabledVegasExecutor:
    """Safe default: never launches Vegas or mutates a project."""

    adapter_name = "disabled-vegas-runtime"

    def execute(
        self, operations: dict[str, Any], working_copy: Path, working_dir: Path
    ) -> dict[str, Any]:
        del operations, working_copy, working_dir
        raise ExecutorDisabledError("Vegas execution is disabled pending E0 human probes")


class ReferenceAudioRenderer:
    """Render a reference WAV with FFmpeg; this is not a Vegas render."""

    adapter_name = "reference-ffmpeg"

    def __init__(self, ffmpeg: str = "ffmpeg") -> None:
        self._ffmpeg = ffmpeg

    def render(
        self,
        *,
        audio_path: Path,
        output_path: Path,
        fps: str,
        duration_frames: int,
        removed: Sequence[FrameInterval],
        fade_ms: int,
    ) -> tuple[int, ...]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return render_cut_audio(
            self._ffmpeg, audio_path, output_path, fps, duration_frames, removed, fade_ms=fade_ms
        ).join_samples


def wait_for_manual_render(
    output_path: Path,
    *,
    working_dir: Path,
    stop_file: Path,
    timeout_s: int,
    poll_s: float = 1.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Path:
    """Wait for a confined, non-empty render file to become size-stable.

    The injected clock and sleep keep timeout behavior testable. This watcher
    does not start Vegas or decide whether the resulting media is correct.
    """
    root = working_dir.resolve()
    candidate = output_path.resolve()
    stop = stop_file.resolve()
    if not candidate.is_relative_to(root) or not stop.is_relative_to(root):
        raise JobStageFailure(
            "render_preview", "E_PATH_CONFINEMENT", "render path escaped the job directory"
        )
    if timeout_s < 1 or timeout_s > 3600 or poll_s <= 0:
        raise JobStageFailure(
            "render_preview", "E_RENDER_TIMEOUT_CONFIG", "render timeout configuration is invalid"
        )
    deadline = clock() + timeout_s
    previous_size = -1
    stable_count = 0
    while clock() < deadline:
        if stop.exists():
            raise JobStageFailure("render_preview", "E_RENDER_STOPPED", "render wait was stopped")
        try:
            current_size = candidate.stat().st_size
        except OSError:
            current_size = 0
        if current_size > 0 and current_size == previous_size:
            stable_count += 1
            if stable_count >= 2:
                return candidate
        else:
            stable_count = 0
        previous_size = current_size
        sleep(min(poll_s, max(0.0, deadline - clock())))
    raise JobStageFailure(
        "render_preview", "E_RENDER_TIMEOUT", "render output did not become ready before timeout"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _atomic_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _load_object(path: Path, stage: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise JobStageFailure(stage, "E_INPUT_READ", f"{label} input could not be read") from None
    if not isinstance(value, dict):
        raise JobStageFailure(stage, "E_INPUT_SHAPE", f"{label} input must be a JSON object")
    return value


def _copy_checked(source: Path, destination: Path, expected_hash: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if _sha256_file(destination) != expected_hash:
        raise JobStageFailure(
            "project_copy", "E_COPY_MISMATCH", "working-copy hash did not match the source"
        )


def _file_record(identifier: str, before: str, after: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "sha256_before": f"sha256:{before}",
        "sha256_after": f"sha256:{after}",
        "unchanged": before == after,
    }


def _manifest(
    *,
    job_id: str,
    input_hashes: Mapping[str, str],
    source_records: Sequence[dict[str, Any]],
    state: Mapping[str, Any],
    pack_characters: int,
    final_status: str,
    message: str,
    code: str | None = None,
) -> dict[str, Any]:
    stage_rows: list[dict[str, Any]] = []
    for name, record in state.get("stages", {}).items():
        status = record.get("status", "partial")
        outcome = (
            "complete" if status == "complete" else "failed" if status == "failed" else "partial"
        )
        row: dict[str, Any] = {
            "name": name,
            "wall_clock_ms": int(record.get("wall_clock_ms", 0)),
            "outcome": outcome,
        }
        if outcome == "failed" and isinstance(record.get("error_code"), str):
            row["error_code"] = record["error_code"]
        stage_rows.append(row)
    if not stage_rows:
        stage_rows.append({"name": "created", "wall_clock_ms": 0, "outcome": "partial"})
    project = source_records[0]
    return {
        "schema_version": "1.1.0",
        "job_id": job_id,
        "inputs": [{"id": key, "sha256": value} for key, value in input_hashes.items()],
        "schemas": {"timeline": "1.0.0", "words": "2.0.0", "edl": "1.2.0", "ops": "1.1.0"},
        "tools": {
            "python": sys.version.split()[0],
            "ffmpeg": "used by renderer adapter or not-run",
            "ffprobe": "not-run",
            "asr_engine": "precomputed words artifact",
            "asr_model": "not-run",
            "align_model": "not-run",
        },
        "stages": stage_rows,
        "token_estimate": {
            "pack_characters": pack_characters,
            "estimated_tokens": (pack_characters + 3) // 4,
            "method": "ceil_chars_div_4",
        },
        "source_integrity": {
            "sha256_before": project["sha256_before"],
            "sha256_after": project["sha256_after"],
            "unchanged": project["unchanged"],
            "files": list(source_records),
        },
        "outcome": {"status": final_status, "code": code, "message": message},
    }


def _stage_is_cached(root: Path, state: Mapping[str, Any], name: str, key: str) -> bool:
    record = state.get("stages", {}).get(name)
    if (
        not isinstance(record, dict)
        or record.get("status") != "complete"
        or record.get("input_key") != key
    ):
        return False
    outputs = record.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        return False
    for relative, digest in outputs.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            return False
        try:
            if _sha256_file(path) != digest:
                return False
        except OSError:
            return False
    return True


def _reuse_mutated_working_copy_checkpoint(
    root: Path, state: dict[str, Any], copy_path: Path
) -> None:
    """Keep an executed working copy when it matches its last recorded checkpoint."""
    checkpoint = state.get("working_copy_checkpoint")
    project_stage = state.get("stages", {}).get("project_copy")
    if not isinstance(checkpoint, dict) or not isinstance(project_stage, dict):
        return
    relative = "working_copy/project.veg"
    expected = checkpoint.get("sha256")
    target = (root / relative).resolve()
    if (
        checkpoint.get("path") != relative
        or not isinstance(expected, str)
        or not target.is_relative_to(root.resolve())
        or not target.is_file()
    ):
        return
    try:
        actual = _sha256_file(target)
    except OSError:
        return
    if actual != expected:
        return
    outputs = project_stage.get("outputs")
    if isinstance(outputs, dict) and relative in outputs:
        outputs[relative] = expected


def _execute_stage(
    root: Path,
    state: dict[str, Any],
    name: str,
    key: str,
    output_paths: Sequence[Path],
    producer: Callable[[], None],
) -> bool:
    """Run a stage unless all recorded output hashes still match."""
    if _stage_is_cached(root, state, name, key):
        state.setdefault("cache_hits", []).append(name)
        return False
    started = time.perf_counter()
    state["current_stage"] = name
    state["status"] = "running"
    state.setdefault("stages", {})[name] = {"status": "running", "input_key": key}
    _atomic_json(root / "job_state.json", state)
    try:
        producer()
        outputs: dict[str, str] = {}
        for output in output_paths:
            resolved = output.resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
                raise JobStageFailure(
                    name, "E_STAGE_OUTPUT", "stage did not create a confined output artifact"
                )
            outputs[str(resolved.relative_to(root.resolve())).replace("\\", "/")] = _sha256_file(
                resolved
            )
    except JobStageFailure as error:
        state["status"] = "failed"
        state["error"] = {"stage": error.stage, "code": error.code, "message": error.message}
        state["stages"][name] = {
            "status": "failed",
            "input_key": key,
            "error_code": error.code,
            "wall_clock_ms": round((time.perf_counter() - started) * 1000),
        }
        _atomic_json(root / "job_state.json", state)
        raise
    except (OSError, ValueError, TypeError, KeyError) as error:
        del error
        failure = JobStageFailure(
            name, "E_STAGE_FAILED", "stage failed; inspect the local run artifacts"
        )
        state["status"] = "failed"
        state["error"] = {"stage": name, "code": failure.code, "message": failure.message}
        state["stages"][name] = {
            "status": "failed",
            "input_key": key,
            "error_code": failure.code,
            "wall_clock_ms": round((time.perf_counter() - started) * 1000),
        }
        _atomic_json(root / "job_state.json", state)
        raise failure from None
    state["stages"][name] = {
        "status": "complete",
        "input_key": key,
        "outputs": outputs,
        "wall_clock_ms": round((time.perf_counter() - started) * 1000),
    }
    state["current_stage"] = name
    _atomic_json(root / "job_state.json", state)
    return True


def _approved_edl(
    edl: dict[str, Any], decisions: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    items = [*edl.get("cuts", []), *edl.get("gap_actions", [])]
    expected = {item["id"] for item in items}
    rows = decisions.get("decisions")
    if not isinstance(rows, list):
        raise JobStageFailure("approve", "E_APPROVAL_SHAPE", "approval file has an invalid shape")
    by_id: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise JobStageFailure(
                "approve", "E_APPROVAL_SHAPE", "approval row has an invalid shape"
            )
        identifier = row["id"]
        choice = row.get("decision")
        if identifier in by_id or choice not in {"approve", "reject"}:
            raise JobStageFailure(
                "approve", "E_APPROVAL_INVALID", "approval contains a duplicate or invalid decision"
            )
        by_id[identifier] = choice
    if set(by_id) != expected:
        raise JobStageFailure(
            "approve", "E_APPROVAL_COVERAGE", "approval must decide every planned cut exactly once"
        )
    approved_ids = {identifier for identifier, choice in by_id.items() if choice == "approve"}
    accepted = dict(edl)
    accepted["cuts"] = [item for item in edl.get("cuts", []) if item["id"] in approved_ids]
    accepted["gap_actions"] = [
        item for item in edl.get("gap_actions", []) if item["id"] in approved_ids
    ]
    metadata = {item["id"]: item for item in items}
    audit = [
        {
            "id": identifier,
            "decision": by_id[identifier],
            "category": metadata[identifier].get("category", "other"),
            "confidence": metadata[identifier].get("confidence", 0.0),
        }
        for identifier in sorted(by_id)
    ]
    return accepted, audit


def _widen_crossfade(current_ms: int, maximum_ms: int) -> int | None:
    if current_ms >= maximum_ms:
        return None
    return min(maximum_ms, max(current_ms + 10, current_ms * 2))


def _write_decision_review(
    *,
    root: Path,
    approved_edl: dict[str, Any],
    words: dict[str, Any],
    report: dict[str, Any],
    fps: str,
    ops: dict[str, Any],
    audit: list[dict[str, Any]],
) -> None:
    write_markers(root / "markers.csv", ops["operations"], fps, decisions=audit)
    write_review(root / "review.md", approved_edl, words, report)
    with (root / "review.md").open("a", encoding="utf-8") as review:
        review.write("\n## Approval decisions\n\n")
        review.write("| Item | Decision |\n|---|---|\n")
        for row in audit:
            review.write(f"| {row['id']} | {row['decision']} |\n")


def run_job(
    *,
    project_path: str | Path,
    source_media_paths: Sequence[str | Path],
    timeline_path: str | Path,
    words_path: str | Path,
    audio_path: str | Path,
    run_dir: str | Path,
    options: JobOptions | None = None,
    planner: Planner | None = None,
    recorded_edl_path: str | Path | None = None,
    decisions_path: str | Path | None = None,
    executor: JobExecutor | None = None,
    renderer: AudioRenderer | None = None,
    resume: bool = False,
) -> Path:
    """Run M4 stages using supplied timeline/perception artifacts.

    This function never opens Vegas. A review-mode caller must inject an
    executor; the default executor fails closed. run_dir is the declared
    working directory for copied projects and generated artifacts.
    """
    options = options or JobOptions()
    if options.mode not in {"dry-run", "review"}:
        raise ValueError("mode must be dry-run or review")
    if not 0 <= options.max_fix_iterations <= 2:
        raise ValueError("max_fix_iterations must be between 0 and 2")
    if options.initial_crossfade_ms < 0 or options.max_crossfade_ms < options.initial_crossfade_ms:
        raise ValueError("crossfade bounds are invalid")
    if not source_media_paths:
        raise ValueError("at least one source media file is required for integrity checks")

    project = Path(project_path).resolve()
    media_files = [Path(path).resolve() for path in source_media_paths]
    timeline_input = Path(timeline_path).resolve()
    words_input = Path(words_path).resolve()
    audio = Path(audio_path).resolve()
    root = Path(run_dir).resolve()
    if project.suffix.casefold() != ".veg" or not project.is_file():
        raise JobStageFailure(
            "project_copy",
            "E_PROJECT_INPUT",
            "project input must be an existing VEGAS project copy",
        )
    if any(not path.is_file() for path in [*media_files, timeline_input, words_input, audio]):
        raise JobStageFailure("ingest", "E_INPUT_MISSING", "a declared input file is missing")
    if root.exists() and not resume:
        raise JobStageFailure(
            "project_copy",
            "E_RUN_EXISTS",
            "run directory already exists; use resume for a saved run",
        )
    root.mkdir(parents=True, exist_ok=True)

    project_hash_before = _sha256_file(project)
    input_hashes = {"project": project_hash_before}
    source_records: list[dict[str, Any]] = [
        _file_record("project", project_hash_before, project_hash_before)
    ]
    for index, media in enumerate(media_files):
        identifier = f"media_{index}"
        digest = _sha256_file(media)
        input_hashes[identifier] = digest
        source_records.append(_file_record(identifier, digest, digest))
    audio_hash = _sha256_file(audio)
    input_hashes["normalized_audio"] = audio_hash
    source_records.append(_file_record("normalized_audio", audio_hash, audio_hash))
    input_hashes["timeline"] = _sha256_file(timeline_input)
    input_hashes["words"] = _sha256_file(words_input)
    if recorded_edl_path is not None:
        input_hashes["recorded_edl"] = _sha256_file(Path(recorded_edl_path).resolve())

    state_path = root / "job_state.json"
    if resume:
        if not state_path.is_file():
            raise JobStageFailure("project_copy", "E_RESUME_STATE", "saved job state is missing")
        state = _load_object(state_path, "project_copy", "saved job state")
        saved_inputs = state.get("inputs", {})
        core_keys = {"project", "normalized_audio", "timeline", "words"} | {
            key for key in input_hashes if key.startswith("media_") or key == "recorded_edl"
        }
        if not isinstance(saved_inputs, dict) or any(
            saved_inputs.get(key) != input_hashes.get(key) for key in core_keys
        ):
            raise JobStageFailure(
                "project_copy", "E_RESUME_INPUT_CHANGED", "resume inputs differ from the saved run"
            )
        state["inputs"] = input_hashes
    else:
        state = {
            "schema_version": "1.0.0",
            "job_id": "job_" + hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16],
            "status": "created",
            "current_stage": "created",
            "inputs": input_hashes,
            "stages": {},
            "cache_hits": [],
            "fixes": [],
        }
        _atomic_json(state_path, state)

    job_id = str(state["job_id"])
    job_id = (
        "".join(ch for ch in job_id if ch.isalnum() or ch in "_-")[:80]
        or "job_" + uuid.uuid4().hex[:12]
    )
    copy_path = root / "working_copy" / "project.veg"
    pre_execute_checkpoint = root / "checkpoints" / "pre_execute.veg"
    if resume:
        _reuse_mutated_working_copy_checkpoint(root, state, copy_path)
    planner_value = planner or BaselinePlanner()
    renderer_value = renderer or ReferenceAudioRenderer()
    executor_value = executor or DisabledVegasExecutor()
    pack_text = ""
    timeline: dict[str, Any] = {}
    words: dict[str, Any] = {}
    edl: dict[str, Any] = {}
    ops: dict[str, Any] = {}
    compile_report: dict[str, Any] = {}
    removed: list[FrameInterval] = []
    final_message = (
        "Offline pipeline complete; Vegas execution and final rendering remain unverified."
    )

    def record_manifest(
        status: str = "partial", message: str | None = None, code: str | None = None
    ) -> None:
        after_records = [_file_record("project", project_hash_before, _sha256_file(project))]
        for index, media in enumerate(media_files):
            after_records.append(
                _file_record(f"media_{index}", input_hashes[f"media_{index}"], _sha256_file(media))
            )
        after_records.append(_file_record("normalized_audio", audio_hash, _sha256_file(audio)))
        unchanged = all(row["unchanged"] for row in after_records)
        manifest = _manifest(
            job_id=job_id,
            input_hashes={key: value for key, value in input_hashes.items() if key != "decisions"},
            source_records=after_records,
            state=state,
            pack_characters=len(pack_text),
            final_status="failed" if not unchanged else status,
            message="source integrity changed during the run"
            if not unchanged
            else (message or final_message),
            code="E_SOURCE_CHANGED" if not unchanged else code,
        )
        issues = [*validate("run_manifest", manifest), *check_run_manifest(manifest)]
        if issues:
            raise JobStageFailure(
                "manifest", "E_MANIFEST_INVALID", "run manifest failed contract validation"
            )
        write_json(root / "run_manifest.json", manifest)
        if not unchanged:
            raise JobStageFailure(
                "integrity", "E_SOURCE_CHANGED", "a source file changed during the run"
            )

    def pause_if_requested(name: str) -> None:
        if options.stop_after_stage == name:
            state["status"] = "paused"
            state["current_stage"] = name
            _atomic_json(state_path, state)
            record_manifest("partial", f"Run paused after {name}; resume with the same inputs.")
            raise JobPaused(name)

    try:
        copy_key = _stable_hash(
            {"project": project_hash_before, "destination": "working_copy/project.veg"}
        )
        _execute_stage(
            root,
            state,
            "project_copy",
            copy_key,
            [copy_path],
            lambda: _copy_checked(project, copy_path, project_hash_before),
        )
        pause_if_requested("project_copy")

        def load_timeline() -> None:
            nonlocal timeline
            timeline = _load_object(timeline_input, "ingest", "timeline")
            issues = [*validate("timeline", timeline), *check_timeline(timeline)]
            if issues:
                raise JobStageFailure(
                    "ingest", "E_TIMELINE_INVALID", "timeline artifact failed contract validation"
                )
            if timeline.get("source_hash") != f"sha256:{input_hashes['media_0']}":
                raise JobStageFailure(
                    "ingest",
                    "E_MEDIA_HASH_MISMATCH",
                    "timeline source hash does not match the declared source media",
                )
            write_json(root / "timeline.json", timeline)

        _execute_stage(
            root,
            state,
            "ingest",
            input_hashes["timeline"] + input_hashes["media_0"],
            [root / "timeline.json"],
            load_timeline,
        )
        pause_if_requested("ingest")
        if not timeline:
            timeline = _load_object(root / "timeline.json", "ingest", "timeline")

        def load_words() -> None:
            nonlocal words
            words = _load_object(words_input, "perceive", "words")
            issues = [*validate("words", words), *check_words(words)]
            if issues:
                raise JobStageFailure(
                    "perceive", "E_WORDS_INVALID", "word artifact failed contract validation"
                )
            if words.get("source_hash") != timeline.get("source_hash") or words.get(
                "fps"
            ) != timeline.get("fps"):
                raise JobStageFailure(
                    "perceive",
                    "E_WORDS_TIMELINE_MISMATCH",
                    "word and timeline source metadata differ",
                )
            write_json(root / "words.json", words)

        _execute_stage(
            root,
            state,
            "perceive",
            input_hashes["words"] + input_hashes["timeline"],
            [root / "words.json"],
            load_words,
        )
        pause_if_requested("perceive")
        if not words:
            words = _load_object(root / "words.json", "perceive", "words")

        def make_pack() -> None:
            nonlocal pack_text
            pack_text = build_pack(words).text
            (root / "pack.txt").write_text(pack_text, encoding="utf-8")

        _execute_stage(
            root,
            state,
            "pack",
            _stable_hash({"words": input_hashes["words"], "version": 1}),
            [root / "pack.txt"],
            make_pack,
        )
        pause_if_requested("pack")
        if not pack_text:
            pack_text = (root / "pack.txt").read_text(encoding="utf-8")

        catalog: dict[str, Any] = {
            "transitions": [],
            "video_fx": [],
            "audio_fx": [],
            "text_presets": [],
            "sfx": [],
        }

        def make_plan() -> None:
            nonlocal edl
            try:
                edl = planner_value.plan(pack_text, words, catalog)
            except PlannerError:
                raise JobStageFailure(
                    "plan", "E_PLAN_FAILED", "planner rejected the offline inputs"
                ) from None
            issues = [
                *validate("edl", edl),
                *check_edl_against(edl, words, {"speakers": {}}, catalog, timeline),
            ]
            if issues:
                raise JobStageFailure(
                    "plan", "E_EDL_INVALID", "planner output failed EDL validation"
                )
            write_json(root / "edl.json", edl)

        plan_key = _stable_hash(
            {
                "pack": input_hashes["words"],
                "planner": type(planner_value).__name__,
                "recorded": input_hashes.get("recorded_edl"),
            }
        )
        _execute_stage(root, state, "plan", plan_key, [root / "edl.json"], make_plan)
        pause_if_requested("plan")
        if not edl:
            edl = _load_object(root / "edl.json", "plan", "EDL")

        def compile_initial() -> None:
            nonlocal ops, compile_report, removed
            ops, compile_report, removed = compile_edl(
                edl,
                words,
                timeline,
                job_id=job_id,
                working_copy_path=str(copy_path),
                config=CompileConfig(audio_crossfade_ms=options.initial_crossfade_ms),
            )
            issues = [
                *validate("ops", ops),
                *check_ops(ops, root),
                *validate("compile_report", compile_report),
            ]
            if issues:
                raise JobStageFailure(
                    "compile", "E_COMPILE_INVALID", "compiled operations failed contract validation"
                )
            write_json(root / "ops.json", ops)
            write_json(root / "compile_report.json", compile_report)

        compile_key = _stable_hash(
            {
                "edl": input_hashes["words"] + _stable_hash(edl),
                "timeline": input_hashes["timeline"],
                "crossfade_ms": options.initial_crossfade_ms,
            }
        )
        _execute_stage(
            root,
            state,
            "compile",
            compile_key,
            [root / "ops.json", root / "compile_report.json"],
            compile_initial,
        )
        pause_if_requested("compile")
        if not ops:
            ops = _load_object(root / "ops.json", "compile", "operations")
            compile_report = _load_object(root / "compile_report.json", "compile", "compile report")
            _, _, removed = compile_edl(
                edl,
                words,
                timeline,
                job_id=job_id,
                working_copy_path=str(copy_path),
                config=CompileConfig(audio_crossfade_ms=options.initial_crossfade_ms),
            )

        def write_preview_artifacts() -> None:
            decisions = [*edl.get("cuts", []), *edl.get("gap_actions", [])]
            write_markers(
                root / "markers_preview.csv",
                ops["operations"],
                timeline["fps"],
                decisions=decisions,
            )
            write_cmx_edl(
                root / "cutlist_preview.edl", timeline["fps"], timeline["duration_frames"], removed
            )
            write_review(root / "review_preview.md", edl, words, compile_report)
            shutil.copyfile(root / "markers_preview.csv", root / "markers.csv")
            shutil.copyfile(root / "review_preview.md", root / "review.md")

        _execute_stage(
            root,
            state,
            "dry_run",
            _stable_hash({"ops": _sha256_file(root / "ops.json"), "words": input_hashes["words"]}),
            [
                root / "markers_preview.csv",
                root / "cutlist_preview.edl",
                root / "review_preview.md",
            ],
            write_preview_artifacts,
        )
        pause_if_requested("dry_run")

        active_edl = edl
        active_ops = ops
        active_report = compile_report
        active_removed = removed
        audit: list[dict[str, Any]] = []
        if options.mode == "review":
            if decisions_path is None:
                template = {
                    "decisions": [
                        {"id": item["id"], "decision": ""}
                        for item in [*edl.get("cuts", []), *edl.get("gap_actions", [])]
                    ]
                }
                _atomic_json(root / "approved_cuts.template.json", template)
                state["status"] = "awaiting_user"
                state["current_stage"] = "approve"
                state.setdefault("stages", {})["approve"] = {
                    "status": "awaiting_user",
                    "input_key": _stable_hash(edl),
                }
                _atomic_json(state_path, state)
                final_message = (
                    "Review artifacts are ready; provide one approval decision per planned cut."
                )
                record_manifest(message=final_message)
                return root

            decisions_file = Path(decisions_path).resolve()
            decisions = _load_object(decisions_file, "approve", "approval")
            active_edl, audit = _approved_edl(edl, decisions)

            def compile_approved() -> None:
                nonlocal active_ops, active_report, active_removed
                active_ops, active_report, active_removed = compile_edl(
                    active_edl,
                    words,
                    timeline,
                    job_id=job_id,
                    working_copy_path=str(copy_path),
                    config=CompileConfig(audio_crossfade_ms=options.initial_crossfade_ms),
                )
                issues = [
                    *validate("ops", active_ops),
                    *check_ops(active_ops, root),
                    *validate("compile_report", active_report),
                ]
                if issues:
                    raise JobStageFailure(
                        "approve",
                        "E_APPROVED_COMPILE_INVALID",
                        "approved cuts failed compile validation",
                    )
                write_json(root / "approved_edl.json", active_edl)
                write_json(root / "approved_ops.json", active_ops)
                write_json(root / "approved_compile_report.json", active_report)
                _copy_checked(project, pre_execute_checkpoint, project_hash_before)
                _atomic_json(root / "approved_cuts.json", {"decisions": audit})
                _write_decision_review(
                    root=root,
                    approved_edl=active_edl,
                    words=words,
                    report=active_report,
                    fps=timeline["fps"],
                    ops=active_ops,
                    audit=audit,
                )

            decision_hash = _sha256_file(decisions_file)
            _execute_stage(
                root,
                state,
                "approve",
                _stable_hash({"edl": _stable_hash(edl), "decisions": decision_hash}),
                [
                    root / "approved_edl.json",
                    root / "approved_ops.json",
                    root / "approved_compile_report.json",
                    pre_execute_checkpoint,
                    root / "approved_cuts.json",
                    root / "markers.csv",
                    root / "review.md",
                ],
                compile_approved,
            )
            pause_if_requested("approve")

            def execute_batch(operations: dict[str, Any]) -> dict[str, Any]:
                issues = [*validate("ops", operations), *check_ops(operations, root)]
                if issues:
                    raise JobStageFailure(
                        "execute",
                        "E_EXECUTOR_INPUT_INVALID",
                        "operation batch failed executor-side validation",
                    )
                try:
                    result = executor_value.execute(operations, copy_path, root)
                except ExecutorDisabledError as error:
                    raise JobStageFailure("execute", "E_EXECUTOR_DISABLED", str(error)) from None
                if not isinstance(result, dict):
                    raise JobStageFailure(
                        "execute", "E_EXECUTOR_RESULT", "executor result has an invalid shape"
                    )
                return result

            def execute_approved() -> None:
                _copy_checked(pre_execute_checkpoint, copy_path, project_hash_before)
                result = execute_batch(active_ops)
                result.setdefault("adapter", executor_value.adapter_name)
                result.setdefault("runtime_evidence", "ASSUMED (RV-001)")
                write_json(root / "execution_result.json", result)

            _execute_stage(
                root,
                state,
                "execute",
                _stable_hash(
                    {
                        "ops": _sha256_file(root / "approved_ops.json"),
                        "executor": executor_value.adapter_name,
                    }
                ),
                [root / "execution_result.json"],
                execute_approved,
            )
            state["working_copy_checkpoint"] = {
                "path": "working_copy/project.veg",
                "sha256": _sha256_file(copy_path),
            }
            _atomic_json(state_path, state)
            pause_if_requested("execute")
        else:
            write_json(
                root / "execution_result.json",
                {
                    "adapter": "none",
                    "status": "skipped_dry_run",
                    "runtime_evidence": "ASSUMED (RV-001)",
                },
            )

        fix_records: list[dict[str, Any]] = []
        current_crossfade = options.initial_crossfade_ms
        final_verify: dict[str, Any] = {}
        final_preview = root / "reference_preview.wav"

        def render_and_verify() -> None:
            nonlocal \
                active_ops, \
                active_report, \
                active_removed, \
                final_verify, \
                current_crossfade, \
                final_preview
            attempts = 0
            while True:
                if attempts > 0:
                    active_ops, active_report, active_removed = compile_edl(
                        active_edl,
                        words,
                        timeline,
                        job_id=job_id,
                        working_copy_path=str(copy_path),
                        config=CompileConfig(audio_crossfade_ms=current_crossfade),
                    )
                    issues = [
                        *validate("ops", active_ops),
                        *check_ops(active_ops, root),
                        *validate("compile_report", active_report),
                    ]
                    if issues:
                        raise JobStageFailure(
                            "verify", "E_COMPILE_INVALID", "recompiled repair ops failed validation"
                        )
                    if options.mode == "review":
                        _copy_checked(pre_execute_checkpoint, copy_path, project_hash_before)
                        execute_batch(active_ops)
                        fix_records[-1]["reexecuted_from_checkpoint"] = True
                        state["working_copy_checkpoint"] = {
                            "path": "working_copy/project.veg",
                            "sha256": _sha256_file(copy_path),
                        }
                        _atomic_json(state_path, state)
                attempt_path = root / f"reference_preview_{attempts}.wav"
                try:
                    join_samples = renderer_value.render(
                        audio_path=audio,
                        output_path=attempt_path,
                        fps=timeline["fps"],
                        duration_frames=timeline["duration_frames"],
                        removed=active_removed,
                        fade_ms=current_crossfade,
                    )
                    report = verify_audio(
                        attempt_path,
                        join_samples,
                        removed_percent=float(active_report["removed_percent"]),
                        max_removed_percent=35.0,
                        words=words,
                        fps=timeline["fps"],
                        removed=active_removed,
                    )
                except (RenderError, OSError, ValueError, wave.Error):
                    raise JobStageFailure(
                        "verify",
                        "E_PREVIEW_VERIFY",
                        "rendered audio could not be read for verification",
                    ) from None
                write_json(root / f"verify_report_{attempts}.json", report)
                final_verify = report
                final_preview = attempt_path
                if report.get("passed") is True or attempts >= options.max_fix_iterations:
                    break
                failed = [
                    item
                    for item in report.get("checks", [])
                    if item.get("passed") is False
                    and item.get("name") in {"click_discontinuity", "level_step"}
                ]
                if not failed:
                    break
                widened = _widen_crossfade(current_crossfade, options.max_crossfade_ms)
                if widened is None:
                    break
                fix_records.append(
                    {
                        "iteration": attempts + 1,
                        "action": "widen_crossfade",
                        "from_ms": current_crossfade,
                        "to_ms": widened,
                        "triggered_by": [str(item.get("id", "unknown")) for item in failed],
                    }
                )
                current_crossfade = widened
                attempts += 1
            shutil.copyfile(final_preview, root / "preview.wav")
            if options.mode == "review":
                write_json(root / "approved_ops.json", active_ops)
                write_json(root / "approved_compile_report.json", active_report)
            else:
                write_json(root / "ops.json", active_ops)
                write_json(root / "compile_report.json", active_report)
            write_json(root / "verify_report.json", final_verify)
            write_json(
                root / "fixes.json",
                {
                    "schema_version": "1.0.0",
                    "max_iterations": options.max_fix_iterations,
                    "fixes": fix_records,
                    "final_crossfade_ms": current_crossfade,
                },
            )

        _execute_stage(
            root,
            state,
            "verify_fix_loop",
            _stable_hash(
                {
                    "ops": _sha256_file(
                        root / ("approved_ops.json" if options.mode == "review" else "ops.json")
                    ),
                    "audio": audio_hash,
                    "iterations": options.max_fix_iterations,
                    "crossfade_max": options.max_crossfade_ms,
                    "renderer": renderer_value.adapter_name,
                }
            ),
            [root / "preview.wav", root / "verify_report.json", root / "fixes.json"],
            render_and_verify,
        )
        pause_if_requested("verify_fix_loop")
        if not final_verify and (root / "verify_report.json").is_file():
            final_verify = _load_object(
                root / "verify_report.json", "verify", "verification report"
            )
            fixes_doc = _load_object(root / "fixes.json", "verify", "fix report")
            current_crossfade = int(
                fixes_doc.get("final_crossfade_ms", options.initial_crossfade_ms)
            )
            if options.mode == "review":
                active_ops = _load_object(
                    root / "approved_ops.json", "verify", "approved operations"
                )
                active_report = _load_object(
                    root / "approved_compile_report.json", "verify", "approved compile report"
                )
            else:
                active_ops = _load_object(root / "ops.json", "verify", "operations")
                active_report = _load_object(
                    root / "compile_report.json", "verify", "compile report"
                )

        def write_final_status() -> None:
            status = (
                "awaiting_manual_vegas_render" if options.mode == "review" else "awaiting_approval"
            )
            write_json(
                root / "final_render_status.json",
                {
                    "status": status,
                    "renderer": "manual-vegas-render-required",
                    "runtime_evidence": "ASSUMED (RV-001)",
                    "expected_output": "final_render.mp4",
                    "message": "No Vegas render was started by this offline runner.",
                },
            )

        _execute_stage(
            root,
            state,
            "render_final",
            _stable_hash(
                {"verify": _sha256_file(root / "verify_report.json"), "mode": options.mode}
            ),
            [root / "final_render_status.json"],
            write_final_status,
        )
        pause_if_requested("render_final")
        state["status"] = "complete_offline"
        state["current_stage"] = "render_final"
        state["fixes"] = fix_records
        _atomic_json(state_path, state)
        final_message = (
            "Offline pipeline complete; fake/reference results do not verify Vegas behavior."
        )
        record_manifest(message=final_message)
        return root
    except JobPaused:
        return root
    except JobStageFailure as error:
        try:
            record_manifest("failed", error.message, error.code)
        except JobStageFailure:
            pass
        raise
