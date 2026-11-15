"""Security regressions for SFX measurement, sidecar confinement, and job state writes."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orchestrator import sfx
from orchestrator.job_pipeline import _atomic_json
from orchestrator.sfx import SfxIndexError, index_sfx_directory


def test_sfx_tool_process_receives_no_credential_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QWEN_VEGAS_API_KEY", "do-not-share")
    monkeypatch.setenv("HF_TOKEN", "do-not-share")
    monkeypatch.setenv("PIP_INDEX_URL", "https://private.invalid")
    monkeypatch.setenv("SAFE_EXAMPLE", "kept")
    calls: list[dict[str, object]] = []

    def fake_run(_command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(kwargs)
        return subprocess.CompletedProcess(_command, 0, "", "")

    monkeypatch.setattr(sfx.subprocess, "run", fake_run)
    sfx._run(["ffprobe", "-version"])
    assert len(calls) == 1
    child_env = calls[0]["env"]
    assert isinstance(child_env, dict)
    assert child_env["SAFE_EXAMPLE"] == "kept"
    assert not any(key in child_env for key in ("QWEN_VEGAS_API_KEY", "HF_TOKEN", "PIP_INDEX_URL"))
    assert calls[0]["shell"] is False
    assert calls[0]["stdin"] == subprocess.DEVNULL


def test_sfx_sidecar_symlink_cannot_read_outside_library(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    audio = library / "tone.wav"
    audio.write_bytes(b"RIFF-test-bytes")
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"license": "CC0-1.0", "source": "private-label"}), encoding="utf-8")
    try:
        audio.with_suffix(".json").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not available for this runner")
    def fake_measure(_path: Path) -> dict[str, float | int]:
        return {"duration": 1.0, "sample_rate": 48000, "loudness_lufs": -23.0, "peak_dbfs": -20.0}
    with pytest.raises(SfxIndexError, match="symbolic link"):
        index_sfx_directory(library, measure=fake_measure)


def test_atomic_json_never_follows_predictable_temporary_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "private_file.json"
    outside.write_text("original contents", encoding="utf-8")
    job = tmp_path / "job"
    job.mkdir()
    target = job / "job_state.json"
    predictable_old_temp = job / "job_state.json.tmp"
    try:
        predictable_old_temp.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not available for this runner")
    _atomic_json(target, {"status": "running"})
    assert outside.read_text(encoding="utf-8") == "original contents"
    assert json.loads(target.read_text(encoding="utf-8")) == {"status": "running"}
    assert predictable_old_temp.is_symlink()
    assert sorted(path.name for path in job.iterdir()) == ["job_state.json", "job_state.json.tmp"]


def test_atomic_json_replaces_state_and_leaves_no_temporary_files(tmp_path: Path) -> None:
    state = tmp_path / "job_state.json"
    _atomic_json(state, {"version": 1})
    _atomic_json(state, {"version": 2})
    assert json.loads(state.read_text(encoding="utf-8")) == {"version": 2}
    assert list(tmp_path.iterdir()) == [state]
