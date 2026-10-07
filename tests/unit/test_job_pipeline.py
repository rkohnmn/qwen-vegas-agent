from __future__ import annotations

import hashlib
import json
import wave
from array import array
from pathlib import Path
from typing import Any

import pytest

import orchestrator.job_pipeline as job_pipeline
from orchestrator.job_pipeline import (
    JobOptions,
    JobStageFailure,
    run_job,
    wait_for_manual_render,
)
from orchestrator.planner import PlannerError
from orchestrator.renderer import RenderError
from orchestrator.verifier import verify_audio

ROOT = Path(__file__).resolve().parents[2]


def _write_wave(path: Path, samples: array[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(samples.tobytes())


class FakeRenderer:
    adapter_name = "FakeRenderer"

    def __init__(self, *, repair_at_ms: int = 40) -> None:
        self.repair_at_ms = repair_at_ms
        self.calls: list[int] = []

    def render(
        self,
        *,
        audio_path: Path,
        output_path: Path,
        fps: str,
        duration_frames: int,
        removed: Any,
        fade_ms: int,
    ) -> tuple[int, ...]:
        del audio_path, fps, duration_frames, removed
        self.calls.append(fade_ms)
        point = 12000
        samples = array("h", [10000] * 48000)
        samples[point:] = array("h", [30000] * (len(samples) - point))
        if fade_ms >= self.repair_at_ms:
            radius = fade_ms * 16
            start = point - radius
            end = point + radius
            span = end - start
            for index in range(start, end):
                fraction = (index - start) / span
                samples[index] = int(10000 + fraction * 20000)
        _write_wave(output_path, samples)
        return (point,)


class FakeExecutor:
    adapter_name = "FakeExecutor"

    def __init__(self, *, mutate_working_copy: bool = False) -> None:
        self.operation_batches: list[dict[str, Any]] = []
        self.mutate_working_copy = mutate_working_copy

    def execute(
        self, operations: dict[str, Any], working_copy: Path, working_dir: Path
    ) -> dict[str, Any]:
        assert working_copy.resolve().is_relative_to(working_dir.resolve())
        self.operation_batches.append(operations)
        if self.mutate_working_copy:
            working_copy.write_bytes(working_copy.read_bytes() + b"fake-executor-edit")
        return {"status": "simulated", "operation_count": len(operations["operations"])}


class BrokenPlanner:
    def plan(self, pack: str, words: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
        del pack, words, catalog
        raise PlannerError("fixture failure")


def _job_inputs(tmp_path: Path) -> dict[str, Any]:
    project = tmp_path / "source.veg"
    project.write_bytes(b"synthetic disposable project fixture")
    media = tmp_path / "source.mp4"
    media.write_bytes(b"synthetic media bytes")
    media_hash = hashlib.sha256(media.read_bytes()).hexdigest()

    timeline = json.loads((ROOT / "tests/fixtures/timeline/valid_minimal.json").read_text())
    timeline["source_hash"] = "sha256:" + media_hash
    timeline["duration_frames"] = 90
    for event in timeline["events"]:
        event["length_frames"] = 90
    timeline_path = tmp_path / "timeline.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")

    words = json.loads((ROOT / "tests/fixtures/words/valid_minimal.json").read_text())
    rows = words["words"][:4]
    starts = [(0.10, 0.25), (0.50, 0.60), (0.90, 1.00), (2.10, 2.40)]
    texts = ["We", "um", "uh", "now"]
    for row, (start, end), text in zip(rows, starts, texts, strict=True):
        row["start"] = start
        row["end"] = end
        row["text"] = text
        row["speaker"] = "host"
        row["track"] = "Mic 1"
    words["words"] = rows
    words["segments"] = [{"id": "s1", "word_ids": [row["id"] for row in rows], "speaker": "host"}]
    words["gaps"] = []
    words["audio_events"] = []
    words["source_hash"] = "sha256:" + media_hash
    words["fps"] = timeline["fps"]
    words_path = tmp_path / "words.json"
    words_path.write_text(json.dumps(words), encoding="utf-8")
    speakers_path = tmp_path / "speakers.json"
    speakers_path.write_text(
        json.dumps(
            {
                "schema_version": "1.1.0",
                "speakers": {"host": {"display": "Host", "color": "#4FC3F7"}},
                "unknown_palette": ["#BDBDBD", "#CE93D8"],
            }
        ),
        encoding="utf-8",
    )

    audio = tmp_path / "normalized.wav"
    _write_wave(audio, array("h", [10000] * 48000))
    return {
        "project_path": project,
        "source_media_paths": [media],
        "timeline_path": timeline_path,
        "words_path": words_path,
        "speakers_path": speakers_path,
        "audio_path": audio,
    }


@pytest.mark.revisit("RV-001")
def test_run_job_writes_review_verify_and_integrity_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _job_inputs(tmp_path)
    renderer = FakeRenderer()
    verify_calls: list[Path] = []
    real_verify = verify_audio

    def verify_from_file(path: str | Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
        artifact = Path(path)
        assert artifact.is_file()
        verify_calls.append(artifact)
        return real_verify(artifact, *args, **kwargs)

    monkeypatch.setattr("orchestrator.job_pipeline.verify_audio", verify_from_file)
    project_before = hashlib.sha256(inputs["project_path"].read_bytes()).hexdigest()
    media_before = hashlib.sha256(inputs["source_media_paths"][0].read_bytes()).hexdigest()
    audio_before = hashlib.sha256(inputs["audio_path"].read_bytes()).hexdigest()

    output = run_job(
        **inputs,
        run_dir=tmp_path / "run",
        renderer=renderer,
        options=JobOptions(initial_crossfade_ms=20, max_crossfade_ms=80),
    )

    expected = {
        "job_state.json",
        "working_copy/project.veg",
        "timeline.json",
        "words.json",
        "speakers.json",
        "pack.txt",
        "edl.json",
        "ops.json",
        "compile_report.json",
        "captions.json",
        "captions.srt",
        "captions.ass",
        "captions_report.json",
        "markers.csv",
        "cutlist_preview.edl",
        "review.md",
        "execution_result.json",
        "preview.wav",
        "verify_report.json",
        "fixes.json",
        "final_render_status.json",
        "run_manifest.json",
    }
    actual = {item.relative_to(output).as_posix() for item in output.rglob("*") if item.is_file()}
    assert expected <= actual
    assert renderer.calls == [20, 40]
    assert verify_calls == [output / "reference_preview_0.wav", output / "reference_preview_1.wav"]
    report = json.loads((output / "verify_report.json").read_text(encoding="utf-8"))
    assert report["passed"] is True
    captions = json.loads((output / "captions.json").read_text(encoding="utf-8"))
    caption_report = json.loads((output / "captions_report.json").read_text(encoding="utf-8"))
    assert captions["captions"]
    assert caption_report["caption_count"] == len(captions["captions"])
    assert "Caption review" in (output / "review.md").read_text(encoding="utf-8")
    fixes = json.loads((output / "fixes.json").read_text(encoding="utf-8"))
    assert fixes["fixes"][0]["action"] == "widen_crossfade"
    assert fixes["fixes"][0]["from_ms"] == 20
    assert fixes["fixes"][0]["to_ms"] == 40

    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_integrity"]["unchanged"] is True
    assert {item["id"] for item in manifest["source_integrity"]["files"]} == {
        "project",
        "media_0",
        "normalized_audio",
    }
    assert all(item["unchanged"] for item in manifest["source_integrity"]["files"])
    assert hashlib.sha256(inputs["project_path"].read_bytes()).hexdigest() == project_before
    assert hashlib.sha256(inputs["source_media_paths"][0].read_bytes()).hexdigest() == media_before
    assert hashlib.sha256(inputs["audio_path"].read_bytes()).hexdigest() == audio_before


@pytest.mark.revisit("RV-001")
def test_approval_recompiles_exact_approved_cut_subset(tmp_path: Path) -> None:
    inputs = _job_inputs(tmp_path)
    decisions = tmp_path / "approved_cuts.json"
    decisions.write_text(
        json.dumps(
            {"decisions": [{"id": "c1", "decision": "approve"}, {"id": "c2", "decision": "reject"}]}
        ),
        encoding="utf-8",
    )
    executor = FakeExecutor()
    output = run_job(
        **inputs,
        run_dir=tmp_path / "review_run",
        options=JobOptions(mode="review", max_fix_iterations=0),
        decisions_path=decisions,
        executor=executor,
        renderer=FakeRenderer(repair_at_ms=0),
    )
    approved = json.loads((output / "approved_ops.json").read_text(encoding="utf-8"))
    approved_captions = json.loads(
        (output / "approved_captions" / "captions.json").read_text(encoding="utf-8")
    )
    assert approved_captions["captions"]
    applied_ids = [
        identifier
        for op in approved["operations"]
        if op["op"] == "delete_range"
        for identifier in op.get("item_ids", [])
    ]
    assert applied_ids == ["c1"]
    assert len(executor.operation_batches) == 1
    review = (output / "review.md").read_text(encoding="utf-8")
    assert "| c1 | approve |" in review
    assert "| c2 | reject |" in review
    marker_labels = (output / "markers.csv").read_text(encoding="utf-8")
    assert "M1_CUT_c1_" in marker_labels
    assert "M1_CUT_c2_" not in marker_labels
    rejected_path = tmp_path / "rejected_cuts.json"
    rejected_path.write_text(
        json.dumps(
            {"decisions": [{"id": "c1", "decision": "reject"}, {"id": "c2", "decision": "reject"}]}
        ),
        encoding="utf-8",
    )
    rejected_executor = FakeExecutor()
    project_before = hashlib.sha256(inputs["project_path"].read_bytes()).hexdigest()
    rejected_output = run_job(
        **inputs,
        run_dir=tmp_path / "all_rejected_run",
        options=JobOptions(mode="review", max_fix_iterations=0),
        decisions_path=rejected_path,
        executor=rejected_executor,
        renderer=FakeRenderer(repair_at_ms=0),
    )
    rejected_ops = json.loads((rejected_output / "approved_ops.json").read_text(encoding="utf-8"))
    assert not any(op["op"] == "delete_range" for op in rejected_ops["operations"])
    assert hashlib.sha256(inputs["project_path"].read_bytes()).hexdigest() == project_before
    assert len(rejected_executor.operation_batches) == 1


@pytest.mark.revisit("RV-001")
def test_review_repair_reexecutes_from_pre_execute_checkpoint(tmp_path: Path) -> None:
    inputs = _job_inputs(tmp_path)
    decisions = tmp_path / "repair_decisions.json"
    decisions.write_text(
        json.dumps(
            {"decisions": [{"id": "c1", "decision": "approve"}, {"id": "c2", "decision": "reject"}]}
        ),
        encoding="utf-8",
    )
    executor = FakeExecutor(mutate_working_copy=True)
    output = run_job(
        **inputs,
        run_dir=tmp_path / "review_repair",
        options=JobOptions(mode="review", max_fix_iterations=2),
        decisions_path=decisions,
        executor=executor,
        renderer=FakeRenderer(repair_at_ms=40),
    )
    assert len(executor.operation_batches) == 2
    assert executor.operation_batches[0] == executor.operation_batches[1]
    state = json.loads((output / "job_state.json").read_text(encoding="utf-8"))
    del state
    checkpoint = output / "checkpoints" / "pre_execute.veg"
    working_copy = output / "working_copy" / "project.veg"
    assert checkpoint.read_bytes() == inputs["project_path"].read_bytes()
    assert working_copy.read_bytes() == inputs["project_path"].read_bytes() + b"fake-executor-edit"
    fixes = json.loads((output / "fixes.json").read_text(encoding="utf-8"))
    assert fixes["fixes"][0]["reexecuted_from_checkpoint"] is True


@pytest.mark.parametrize(
    "stop_stage",
    [
        "project_copy",
        "ingest",
        "perceive",
        "pack",
        "plan",
        "compile",
        "dry_run",
        "approve",
        "execute",
        "verify_fix_loop",
        "render_final",
    ],
)
@pytest.mark.revisit("RV-001")
def test_resume_reuses_hash_checked_completed_stages(tmp_path: Path, stop_stage: str) -> None:
    inputs = _job_inputs(tmp_path)
    run_dir = tmp_path / f"resume_{stop_stage}"
    review_mode = stop_stage in {"approve", "execute"}
    decisions_path = None
    if review_mode:
        decisions_path = tmp_path / f"decisions_{stop_stage}.json"
        decisions_path.write_text(
            json.dumps(
                {
                    "decisions": [
                        {"id": "c1", "decision": "reject"},
                        {"id": "c2", "decision": "reject"},
                    ]
                }
            ),
            encoding="utf-8",
        )
    options = JobOptions(mode="review" if review_mode else "dry-run", stop_after_stage=stop_stage)
    run_job(
        **inputs,
        run_dir=run_dir,
        renderer=FakeRenderer(),
        options=options,
        decisions_path=decisions_path,
        executor=FakeExecutor() if review_mode else None,
    )
    state_before = json.loads((run_dir / "job_state.json").read_text(encoding="utf-8"))
    assert state_before["current_stage"] == stop_stage

    output = run_job(
        **inputs,
        run_dir=run_dir,
        renderer=FakeRenderer(),
        options=JobOptions(mode="review" if review_mode else "dry-run"),
        decisions_path=decisions_path,
        executor=FakeExecutor() if review_mode else None,
        resume=True,
    )
    state_after = json.loads((output / "job_state.json").read_text(encoding="utf-8"))
    assert stop_stage in state_after["cache_hits"]
    assert (output / "run_manifest.json").is_file()


@pytest.mark.revisit("RV-001")
def test_resume_preserves_checkpointed_working_copy_after_fake_execution(
    tmp_path: Path,
) -> None:
    inputs = _job_inputs(tmp_path)
    run_dir = tmp_path / "mutated_resume"
    decisions = tmp_path / "mutated_resume_decisions.json"
    decisions.write_text(
        json.dumps(
            {"decisions": [{"id": "c1", "decision": "reject"}, {"id": "c2", "decision": "reject"}]}
        ),
        encoding="utf-8",
    )
    run_job(
        **inputs,
        run_dir=run_dir,
        options=JobOptions(mode="review", stop_after_stage="execute"),
        decisions_path=decisions,
        executor=FakeExecutor(mutate_working_copy=True),
        renderer=FakeRenderer(repair_at_ms=0),
    )
    working_copy = run_dir / "working_copy" / "project.veg"
    executed_hash = hashlib.sha256(working_copy.read_bytes()).hexdigest()
    assert executed_hash != hashlib.sha256(inputs["project_path"].read_bytes()).hexdigest()

    run_job(
        **inputs,
        run_dir=run_dir,
        options=JobOptions(mode="review"),
        decisions_path=decisions,
        executor=FakeExecutor(),
        renderer=FakeRenderer(repair_at_ms=0),
        resume=True,
    )
    assert hashlib.sha256(working_copy.read_bytes()).hexdigest() == executed_hash


def test_planner_and_executor_failures_have_typed_codes(tmp_path: Path) -> None:
    inputs = _job_inputs(tmp_path)
    with pytest.raises(JobStageFailure, match="planner rejected") as planner_error:
        run_job(
            **inputs,
            run_dir=tmp_path / "planner_failure",
            planner=BrokenPlanner(),  # type: ignore[arg-type]
            renderer=FakeRenderer(),
        )
    assert planner_error.value.code == "E_PLAN_FAILED"

    decisions = tmp_path / "approved_cuts.json"
    decisions.write_text(
        json.dumps(
            {"decisions": [{"id": "c1", "decision": "reject"}, {"id": "c2", "decision": "reject"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(JobStageFailure) as executor_error:
        run_job(
            **inputs,
            run_dir=tmp_path / "executor_failure",
            options=JobOptions(mode="review", max_fix_iterations=0),
            decisions_path=decisions,
            renderer=FakeRenderer(),
        )
    assert executor_error.value.code == "E_EXECUTOR_DISABLED"


@pytest.mark.parametrize(
    ("failure", "expected_stage", "expected_code"),
    [
        ("project_copy", "project_copy", "E_PROJECT_INPUT"),
        ("ingest", "ingest", "E_TIMELINE_INVALID"),
        ("perceive", "perceive", "E_WORDS_INVALID"),
        ("pack", "pack", "E_STAGE_FAILED"),
        ("plan", "plan", "E_PLAN_FAILED"),
        ("compile", "compile", "E_STAGE_FAILED"),
        ("dry_run", "dry_run", "E_STAGE_FAILED"),
        ("approve", "approve", "E_APPROVAL_COVERAGE"),
        ("execute", "execute", "E_EXECUTOR_DISABLED"),
        ("verify_fix_loop", "verify", "E_PREVIEW_VERIFY"),
        ("render_final", "render_final", "E_STAGE_FAILED"),
    ],
)
@pytest.mark.revisit("RV-001")
def test_pipeline_stage_failures_have_typed_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    expected_stage: str,
    expected_code: str,
) -> None:
    inputs = _job_inputs(tmp_path)
    run_dir = tmp_path / f"failure_{failure}"
    options = JobOptions(max_fix_iterations=0)
    decisions_path = None
    renderer: Any = FakeRenderer(repair_at_ms=0)
    executor = None

    if failure == "project_copy":
        inputs["project_path"] = tmp_path / "missing.veg"
    elif failure == "ingest":
        inputs["timeline_path"].write_text("{}", encoding="utf-8")
    elif failure == "perceive":
        inputs["words_path"].write_text("{}", encoding="utf-8")
    elif failure in {"pack", "compile", "dry_run", "render_final"}:

        def fail_operation(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            raise OSError("synthetic failure")

        if failure == "pack":
            monkeypatch.setattr(job_pipeline, "build_pack", fail_operation)
        elif failure == "compile":
            monkeypatch.setattr(job_pipeline, "compile_edl", fail_operation)
        elif failure == "dry_run":
            monkeypatch.setattr(job_pipeline, "write_markers", fail_operation)
        else:
            real_write_json = job_pipeline.write_json

            def fail_final_status(path: Path, document: Any) -> None:
                if Path(path).name == "final_render_status.json":
                    fail_operation()
                real_write_json(path, document)

            monkeypatch.setattr(job_pipeline, "write_json", fail_final_status)
    elif failure == "plan":
        planner = BrokenPlanner()
    elif failure in {"approve", "execute"}:
        options = JobOptions(mode="review", max_fix_iterations=0)
        decisions_path = tmp_path / f"{failure}_decisions.json"
        rows = (
            []
            if failure == "approve"
            else [
                {"id": "c1", "decision": "reject"},
                {"id": "c2", "decision": "reject"},
            ]
        )
        decisions_path.write_text(json.dumps({"decisions": rows}), encoding="utf-8")
    elif failure == "verify_fix_loop":

        class FailingRenderer(FakeRenderer):
            def render(self, **kwargs: Any) -> tuple[int, ...]:
                del kwargs
                raise RenderError("synthetic renderer failure")

        renderer = FailingRenderer()

    kwargs: dict[str, Any] = {}
    if failure == "plan":
        kwargs["planner"] = planner
    if failure == "execute":
        kwargs["executor"] = executor
    with pytest.raises(JobStageFailure) as error:
        run_job(
            **inputs,
            run_dir=run_dir,
            options=options,
            decisions_path=decisions_path,
            renderer=renderer,
            **kwargs,
        )
    assert error.value.stage == expected_stage
    assert error.value.code == expected_code


def test_manual_render_watcher_returns_stable_confined_file(tmp_path: Path) -> None:
    now = [0.0]
    candidate = tmp_path / "manual.wav"

    def clock() -> float:
        return now[0]

    def sleep(duration: float) -> None:
        now[0] += duration
        candidate.write_bytes(b"fixture-wav")

    result = wait_for_manual_render(
        candidate,
        working_dir=tmp_path,
        stop_file=tmp_path / "STOP",
        timeout_s=5,
        poll_s=1,
        clock=clock,
        sleep=sleep,
    )
    assert result == candidate.resolve()
    assert result.read_bytes() == b"fixture-wav"


def test_manual_render_watcher_times_out_with_typed_failure(tmp_path: Path) -> None:
    now = [0.0]

    def clock() -> float:
        return now[0]

    def sleep(duration: float) -> None:
        now[0] += duration

    with pytest.raises(JobStageFailure) as error:
        wait_for_manual_render(
            tmp_path / "not-ready.mp4",
            working_dir=tmp_path,
            stop_file=tmp_path / "STOP",
            timeout_s=2,
            poll_s=1,
            clock=clock,
            sleep=sleep,
        )
    assert error.value.code == "E_RENDER_TIMEOUT"


def test_resume_rejects_changed_input_hashes(tmp_path: Path) -> None:
    inputs = _job_inputs(tmp_path)
    run_dir = tmp_path / "changed_input"
    run_job(
        **inputs,
        run_dir=run_dir,
        renderer=FakeRenderer(),
        options=JobOptions(stop_after_stage="project_copy"),
    )
    inputs["source_media_paths"][0].write_bytes(b"changed")
    with pytest.raises(JobStageFailure) as error:
        run_job(**inputs, run_dir=run_dir, renderer=FakeRenderer(), resume=True)
    assert error.value.code == "E_RESUME_INPUT_CHANGED"


def test_run_job_rejects_timeline_media_hash_mismatch(tmp_path: Path) -> None:
    inputs = _job_inputs(tmp_path)
    timeline = json.loads(inputs["timeline_path"].read_text(encoding="utf-8"))
    timeline["source_hash"] = "sha256:" + ("f" * 64)
    inputs["timeline_path"].write_text(json.dumps(timeline), encoding="utf-8")
    with pytest.raises(JobStageFailure) as error:
        run_job(**inputs, run_dir=tmp_path / "mismatch", renderer=FakeRenderer())
    assert error.value.code == "E_MEDIA_HASH_MISMATCH"
