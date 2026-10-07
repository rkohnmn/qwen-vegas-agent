from __future__ import annotations

import csv
import json
import time
import wave
from array import array
from collections.abc import Iterator
from contextlib import contextmanager
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

from orchestrator.artifacts import write_markers, write_review
from orchestrator.childenv import safe_child_environment
from orchestrator.cli import run_dry_run
from orchestrator.compiler import CompileConfig, compile_edl, frame_to_time, time_to_frame
from orchestrator.contracts import (
    check_compile_report,
    check_edl_against,
    check_ops,
    check_timeline,
    validate,
)
from orchestrator.evaluation import run_synthetic_eval, synthetic_case, truth_template
from orchestrator.packer import build_pack
from orchestrator.planner import (
    BaselinePlanner,
    EndpointAuthError,
    EndpointUnreachable,
    LlmPlanner,
    MalformedPlannerOutput,
    PlannerError,
    RecordedPlanner,
)
from orchestrator.renderer import render_cut_audio
from orchestrator.verifier import verify_audio


def _catalog() -> dict[str, object]:
    return {"transitions": [], "video_fx": [], "audio_fx": [], "text_presets": [], "sfx": []}


def test_frame_math_has_no_drift_for_100000_frames() -> None:
    rate = Fraction(30000, 1001)
    for frame in range(100001):
        assert time_to_frame(frame_to_time(frame, rate), rate) == frame


def test_baseline_pack_and_compile_are_id_only_and_frame_safe(tmp_path: Path) -> None:
    words, timeline, _truth = synthetic_case()
    assert not validate("words", words)
    assert not validate("timeline", timeline)
    assert not check_timeline(timeline)
    pack = build_pack(words)
    assert 'w2 0.280-0.450 unknown "um"' in pack.text
    planner = BaselinePlanner(minimum_gap_ms=650)
    edl = planner.plan(pack.text, words, _catalog())
    assert not validate("edl", edl)
    assert not check_edl_against(edl, words, {"speakers": {}}, _catalog(), timeline)
    ops, report, intervals = compile_edl(
        edl,
        words,
        timeline,
        job_id="unit",
        working_copy_path=str(tmp_path / "working.veg"),
        config=CompileConfig(),
    )
    assert not validate("ops", ops)
    assert not check_ops(ops, tmp_path)
    assert not validate("compile_report", report)
    assert not check_compile_report(report)
    assert len(report["fade_decisions"]) == len(intervals)
    assert len(report["snaps"]) == 4
    assert any(item["code"] == "E_PACING_GAP" for item in report["rejected_items"])
    outcomes = {item["item_id"]: item for item in report["item_outcomes"]}
    proposed_items = [*edl["cuts"], *edl["gap_actions"]]
    assert set(outcomes) == {item["id"] for item in proposed_items}
    assert len(outcomes) == len(proposed_items)
    assert all(item["status"] in {"applied", "adjusted", "rejected"} for item in outcomes.values())
    for action in edl["gap_actions"]:
        assert outcomes[action["id"]]["item_type"] == "gap_action"
    assert outcomes["c1"]["status"] == "rejected"
    assert outcomes["c1"]["code"] == "E_PACING_GAP"
    assert outcomes["c2"]["status"] == "applied"
    delete_operations = [
        operation for operation in ops["operations"] if operation["op"] == "delete_range"
    ]
    assert delete_operations[0]["item_ids"] == ["c2"]
    marker_labels = {
        operation["label"] for operation in ops["operations"] if operation["op"] == "add_marker"
    }
    assert "M1_CUT_c2_silence_IN" in marker_labels
    assert "M1_CUT_c2_silence_OUT" in marker_labels
    marker_path = tmp_path / "markers.csv"
    decisions = [*edl["cuts"], *edl["gap_actions"]]
    write_markers(marker_path, ops["operations"], timeline["fps"], decisions=decisions)
    with marker_path.open(encoding="utf-8", newline="") as marker_file:
        marker_rows = list(csv.DictReader(marker_file))
    assert marker_rows[0]["category"] == "silence"
    assert marker_rows[0]["confidence"] == "0.90"
    assert marker_rows[0]["label"].startswith("M1_CUT_c2_silence_")
    review_path = tmp_path / "review.md"
    write_review(review_path, edl, words, report)
    review = review_path.read_text()
    assert "| Cut count | Total removed frames | Removed percent |" in review
    assert "## Proposed but not applied" in review
    assert "`c1` (cut; filler; word IDs w2 through w2): `E_PACING_GAP`" in review
    assert len(intervals) == 2
    assert intervals[1].start >= 24
    assert intervals[1].end <= 51
    for interval in intervals:
        for word in words["words"]:
            start = int(word["start"] * 30)
            end = int(word["end"] * 30 + 0.999999)
            if interval.start < end and interval.end > start:
                assert interval.start <= start and interval.end >= end


def test_compiler_prefers_nearby_zero_crossing_and_reports_both_boundaries() -> None:
    words, timeline, _truth = synthetic_case()
    pack = build_pack(words)
    edl = BaselinePlanner(minimum_gap_ms=650).plan(pack.text, words, _catalog())
    edl["gap_actions"] = []
    samples = array("h", [1000] * 64000)
    samples[4000:] = array("h", [-1000] * (len(samples) - 4000))
    samples[7680:] = array("h", [1000] * (len(samples) - 7680))
    _ops, report, intervals = compile_edl(
        edl,
        words,
        timeline,
        job_id="zero_crossing",
        working_copy_path="runs/zero_crossing/working_copy.veg",
        config=CompileConfig(min_gap_after_cut_ms=0, snap_zero_crossing=True),
        audio_samples=samples,
        sample_rate=16000,
    )
    assert len(intervals) == 1
    filler_snaps = [snap for snap in report["snaps"] if snap["id"].startswith("c1_")]
    assert {snap["id"] for snap in filler_snaps} == {"c1_in", "c1_out"}
    assert all("nearest zero crossing" in snap["reason"] for snap in filler_snaps)
    filler_outcome = next(item for item in report["item_outcomes"] if item["item_id"] == "c1")
    assert filler_outcome["status"] == "adjusted"
    assert filler_outcome["delta_frames"] > 0


def test_recorded_planner_returns_a_copy() -> None:
    words, _timeline, _truth = synthetic_case()
    pack = build_pack(words)
    response = BaselinePlanner().plan(pack.text, words, _catalog())
    planner = RecordedPlanner(response)
    first = planner.plan(pack.text, words, _catalog())
    first["summary"] = "changed"
    second = planner.plan(pack.text, words, _catalog())
    assert second["summary"] != "changed"


@contextmanager
def _loopback_server(
    handler_type: type[BaseHTTPRequestHandler],
) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_type)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: bytes) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _llm_envelope(content: str) -> bytes:
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode()


def test_llm_planner_uses_loopback_fake_and_rejects_remote() -> None:
    words, _timeline, _truth = synthetic_case()
    response = BaselinePlanner().plan(build_pack(words).text, words, _catalog())
    planner_catalog = _catalog()
    planner_catalog["transitions"] = [
        {"key": "tr.disabled.abcdef12", "enabled": False},
        {"key": "tr.allowed.abcdef34", "enabled": True},
    ]
    planner_catalog["sfx"] = [{"key": "sfx.disabled.abcdef56", "enabled": False}]
    captured: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            captured["authorization"] = self.headers.get("Authorization", "")
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            captured["request"] = request
            assert request["model"] == "test-model"
            _send_json(self, 200, _llm_envelope(json.dumps(response)))

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    feedback = [{"code": "E_PACING_GAP", "path": "$.cuts[0]", "message": "must not be echoed"}]
    test_secret = "local-" + "test-secret"
    with _loopback_server(Handler) as endpoint:
        result = LlmPlanner(endpoint, "test-model", api_key=test_secret, retry_backoff_s=0).plan(
            build_pack(words).text, words, planner_catalog, feedback=feedback
        )
    assert result == response
    assert captured["authorization"] == f"Bearer {test_secret}"
    assert test_secret not in json.dumps(captured["request"])
    request = captured["request"]
    assert isinstance(request, dict)
    correction_messages = [
        message["content"]
        for message in request["messages"]
        if "CORRECTION_ERRORS=" in message["content"]
    ]
    assert len(correction_messages) == 1
    assert "E_PACING_GAP" in correction_messages[0]
    assert "must not be echoed" not in correction_messages[0]
    request_text = json.dumps(request["messages"])
    assert "tr.allowed.abcdef34" in request_text
    assert "tr.disabled.abcdef12" not in request_text
    assert "sfx.disabled.abcdef56" not in request_text
    with pytest.raises(PlannerError) as remote_error:
        LlmPlanner("https://example.com/v1", "test-model")
    assert "example.com" not in str(remote_error.value)


def test_llm_planner_does_not_follow_a_redirect() -> None:
    calls: list[int] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            calls.append(1)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(302)
            self.send_header("Location", "https://example.com/collect")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    words, _timeline, _truth = synthetic_case()
    with _loopback_server(Handler) as endpoint:
        planner = LlmPlanner(endpoint, "test-model", api_key="redirect-secret", max_retries=0)
        with pytest.raises(PlannerError) as error:
            planner.plan(build_pack(words).text, words, _catalog())
    assert len(calls) == 1
    assert "example.com" not in str(error.value)
    assert "redirect-secret" not in str(error.value)


def test_llm_planner_auth_error_is_typed_redacted_and_not_retried() -> None:
    calls: list[int] = []
    secret = "loopback-secret-for-auth-test"
    response_body = f"rejected token {secret}".encode()
    backoffs: list[float] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            calls.append(1)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            _send_json(self, 401, response_body)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    words, _timeline, _truth = synthetic_case()
    with _loopback_server(Handler) as endpoint:
        planner = LlmPlanner(
            endpoint,
            "test-model",
            api_key=secret,
            retry_backoff_s=0.01,
            sleep=backoffs.append,
        )
        with pytest.raises(EndpointAuthError) as error:
            planner.plan(build_pack(words).text, words, _catalog())
    assert len(calls) == 1
    assert backoffs == []
    assert secret not in str(error.value)
    assert "rejected token" not in str(error.value)


def test_llm_planner_timeout_is_typed_and_retried_with_bounded_backoff(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[int] = []
    backoffs: list[float] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            calls.append(1)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            time.sleep(0.12)
            try:
                _send_json(self, 200, _llm_envelope("{}"))
            except OSError:
                pass

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    words, _timeline, _truth = synthetic_case()
    with _loopback_server(Handler) as endpoint:
        planner = LlmPlanner(
            endpoint,
            "test-model",
            api_key="timeout-secret",
            timeout_s=0.03,
            max_retries=1,
            retry_backoff_s=0.01,
            sleep=backoffs.append,
        )
        with pytest.raises(EndpointUnreachable) as error:
            planner.plan(build_pack(words).text, words, _catalog())
    assert len(calls) == 2
    assert backoffs == [0.01]
    assert "timeout-secret" not in str(error.value)
    assert "timeout-secret" not in caplog.text


def test_llm_planner_malformed_json_raises_typed_error_after_retries() -> None:
    calls: list[int] = []
    backoffs: list[float] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            calls.append(1)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            _send_json(self, 200, b"{malformed")

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    words, _timeline, _truth = synthetic_case()
    with _loopback_server(Handler) as endpoint:
        planner = LlmPlanner(
            endpoint, "test-model", max_retries=1, retry_backoff_s=0.01, sleep=backoffs.append
        )
        with pytest.raises(MalformedPlannerOutput):
            planner.plan(build_pack(words).text, words, _catalog())
    assert len(calls) == 2
    assert backoffs == [0.01]


def test_llm_planner_schema_invalid_json_raises_malformed_output() -> None:
    calls: list[int] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            calls.append(1)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            _send_json(self, 200, _llm_envelope(json.dumps({"schema_version": "1.2.0"})))

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    words, _timeline, _truth = synthetic_case()
    with _loopback_server(Handler) as endpoint:
        planner = LlmPlanner(endpoint, "test-model", max_retries=1, retry_backoff_s=0)
        with pytest.raises(MalformedPlannerOutput):
            planner.plan(build_pack(words).text, words, _catalog())
    assert len(calls) == 2


def test_llm_planner_corrects_schema_failure_on_retry() -> None:
    words, _timeline, _truth = synthetic_case()
    valid_edl = BaselinePlanner().plan(build_pack(words).text, words, _catalog())
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            requests.append(request)
            content = json.dumps({"bad": True}) if len(requests) == 1 else json.dumps(valid_edl)
            _send_json(self, 200, _llm_envelope(content))

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    backoffs: list[float] = []
    with _loopback_server(Handler) as endpoint:
        result = LlmPlanner(
            endpoint,
            "test-model",
            max_retries=1,
            retry_backoff_s=0.01,
            sleep=backoffs.append,
        ).plan(build_pack(words).text, words, _catalog())
    assert result == valid_edl
    assert len(requests) == 2
    assert backoffs == [0.01]
    retry_messages = requests[1]["messages"]
    assert isinstance(retry_messages, list)
    correction = retry_messages[-1]["content"]
    assert "CORRECTION_ERRORS=" in correction
    assert "E_SCHEMA" in correction
    assert "must not be echoed" not in correction


def test_llm_planner_missing_server_raises_safe_unreachable_error() -> None:
    words, _timeline, _truth = synthetic_case()
    planner = LlmPlanner(
        "http://127.0.0.1:1/v1",
        "test-model",
        api_key="secret-value",
        max_retries=0,
    )
    with pytest.raises(EndpointUnreachable) as error:
        planner.plan(build_pack(words).text, words, _catalog())
    assert "secret-value" not in str(error.value)


def test_cli_rejects_llm_before_reading_media() -> None:
    with pytest.raises(EndpointUnreachable, match="disabled in M1"):
        run_dry_run("missing-input.mp4", planner_name="llm")


def test_llm_missing_loopback_server_has_safe_error() -> None:
    planner = LlmPlanner("http://127.0.0.1:1/v1", "test-model", api_key="secret-value")
    words, _timeline, _truth = synthetic_case()
    try:
        planner.plan(build_pack(words).text, words, _catalog())
    except PlannerError as error:
        assert "secret-value" not in str(error)
    else:
        raise AssertionError("missing fake server did not fail")


def test_synthetic_eval_and_truth_template() -> None:
    words, _timeline, _truth = synthetic_case()
    template = truth_template(words)
    assert template["expected_cuts"] == []
    report = run_synthetic_eval()
    assert report["cut_precision"] == 1.0
    assert report["cut_recall"] == 1.0
    assert report["applied_precision"] == 1.0
    assert report["applied_recall"] == 0.5
    assert report["proposed_rejected_or_adjusted_count"] == 1
    assert report["proposed_rejected_or_adjusted_percent"] == 50.0
    assert report["clipped_word_rate"] == 0.0
    assert report["click_rate"] == 0.0
    assert report["verifier_passed"] is False
    assert report["failed_verification_checks"] == ["join_1_level", "join_2_level"]
    assert report["wall_clock_ms"] >= 0
    caption_eval = report["caption_sidecars"]
    assert caption_eval["input_words"] == 300
    assert caption_eval["captions"] == 300
    assert caption_eval["srt_ass_round_trip"] == "passed"


def test_reference_renderer_uses_safe_argument_list_and_verifier_checks_every_join(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.wav"
    output = tmp_path / "cut.wav"
    with wave.open(str(source), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(32000 * 2))
    from orchestrator.compiler import FrameInterval

    def fake_run(args: list[str], **kwargs: object):
        assert kwargs["shell"] is False
        assert "-filter_complex" in args
        destination = Path(args[-1])
        with wave.open(str(destination), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(bytes(31680 * 2))
        return type("Completed", (), {"returncode": 0})()

    with patch("orchestrator.renderer.subprocess.run", side_effect=fake_run):
        result = render_cut_audio(
            "ffmpeg",
            source,
            output,
            "30/1",
            30,
            [FrameInterval(10, 20, ("c1",), "filler")],
        )
    assert result.join_samples == (5173,)
    verification = verify_audio(
        output,
        result.join_samples,
        words={
            "words": [
                {
                    "id": "w1",
                    "track": "audio_0",
                    "alignment_status": "aligned",
                    "start": 0.2,
                    "end": 0.3,
                },
                {
                    "id": "w2",
                    "track": "audio_0",
                    "alignment_status": "aligned",
                    "start": 0.8,
                    "end": 0.9,
                },
            ]
        },
        fps="30/1",
        removed=[FrameInterval(10, 20, ("c1",), "filler")],
        min_interword_gap_ms=120,
        max_interword_gap_ms=1800,
    )
    assert len(verification["checks"]) == 7
    assert verification["checks"][0]["name"] == "click_discontinuity"
    assert sum(check["name"] == "pacing" for check in verification["checks"]) == 2
    assert sum(check["name"] == "clipped_word" for check in verification["checks"]) == 2


def test_child_environment_removes_credentials_and_custom_package_indexes() -> None:
    cleaned = safe_child_environment(
        {
            "PATH": "tools",
            "QWEN_VEGAS_API_KEY": "do-not-forward",
            "HF_TOKEN": "do-not-forward",
            "PIP_INDEX_URL": "https://user:password@example.invalid/simple",
            "USERNAME": "editor",
        }
    )
    assert cleaned == {"PATH": "tools", "USERNAME": "editor"}
