from __future__ import annotations

import json
import struct
import tempfile
import time
import wave
from collections.abc import Sequence
from pathlib import Path

import pytest

import tasks
from orchestrator.childenv import safe_child_environment
from orchestrator.contracts import redact, validate
from orchestrator.stages import _has_pending_speaker_question
from perception.speakers import (
    AudioTrack,
    DiarizationTurn,
    EnrollmentError,
    SpeakerError,
    apply_bleed_confidence,
    apply_identification_answer,
    attribute_multitrack_words,
    attribute_words_from_turns,
    build_speaker_report,
    cosine_similarity,
    enroll_samples,
    ensure_unknown_speaker,
    expire_pending_questions,
    make_identify_question,
    match_embedding,
    read_embedding_profile,
    rebuild_segments_by_speaker,
    save_voice_profile,
    select_speaker_mode,
    word_track_energies,
)
from tasks import task_answer_speaker, task_enroll


def _fixture(contract: str, name: str) -> dict[str, object]:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / contract / f"{name}.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _speakers() -> dict[str, object]:
    return {
        "schema_version": "1.1.0",
        "speakers": {
            "host": {"display": "Host", "color": "#4FC3F7", "track": "Mic 1"},
            "guest": {"display": "Guest", "color": "#FFB74D", "track": "Mic 2"},
        },
        "unknown_palette": ["#BDBDBD", "#CE93D8"],
    }


def test_auto_mode_uses_track_mappings_and_hybrid_for_partial_mappings() -> None:
    tracks = [
        AudioTrack("audio_0", "audio_0", ("Mic 1",)),
        AudioTrack("audio_1", "audio_1", ("Mic 2",)),
    ]
    speakers = _speakers()
    assert select_speaker_mode("auto", tracks, speakers).mode == "multitrack"
    partial = {**speakers, "speakers": {"host": speakers["speakers"]["host"]}}
    assert select_speaker_mode("auto", tracks, partial).mode == "hybrid"
    assert select_speaker_mode("single", tracks, speakers).mode == "single"
    assert select_speaker_mode("auto", [tracks[0]], {"speakers": {}}).mode == "single"
    assert select_speaker_mode("auto", tracks, {"speakers": {}}).mode == "diarized"


def test_multitrack_words_use_track_map_and_unknown_stays_low_confidence() -> None:
    words = [
        {"id": "w1", "track": "audio_0", "speaker_conf": 0.0},
        {"id": "w2", "track": "audio_1", "speaker_conf": 0.0},
    ]
    attribute_multitrack_words(words, {"audio_0": "host"})
    assert words[0]["speaker"] == "host"
    assert words[0]["speaker_conf"] == 1.0
    assert words[1]["speaker"] == "unknown_1"
    assert words[1]["speaker_conf"] == 0.25


def test_bleed_candidates_are_kept_and_downranked_for_review() -> None:
    words = [
        {
            "id": "w1",
            "text": "hello",
            "start": 1.0,
            "end": 1.4,
            "track": "audio_0",
            "speaker_conf": 1.0,
        },
        {
            "id": "w2",
            "text": "hello",
            "start": 1.02,
            "end": 1.38,
            "track": "audio_1",
            "speaker_conf": 1.0,
        },
    ]
    reasons = apply_bleed_confidence(
        words,
        {"w1": {"audio_0": 10.0}, "w2": {"audio_1": 100.0}},
    )
    assert len(words) == 2
    assert words[0]["speaker_conf"] == 0.2
    assert reasons == {"w1": "likely_track_bleed"}
    report = build_speaker_report(words, reasons)
    assert report["low_confidence_count"] == 1
    assert report["ranges"][0]["reason"] == "likely_track_bleed"


def test_word_track_energy_uses_pcm_samples_without_model_inference() -> None:
    words = [{"id": "w1", "start": 0.0, "end": 0.04}]
    energies = word_track_energies(words, {"audio_0": [100] * 640, "audio_1": [1000] * 640}, 16000)
    assert energies["w1"]["audio_1"] > energies["w1"]["audio_0"]


def test_diarization_turn_overlap_marks_word_and_reduces_confidence() -> None:
    words = [{"id": "w1", "start": 1.0, "end": 2.0, "speaker": None, "speaker_conf": 0.0}]
    turns = [DiarizationTurn("cluster_a", 1.0, 2.0), DiarizationTurn("cluster_b", 1.5, 2.0)]
    attribute_words_from_turns(words, turns, {"cluster_a": "host", "cluster_b": "guest"})
    assert words[0]["speaker"] == "host"
    assert words[0]["overlap"] is True
    assert words[0]["speaker_conf"] == 0.5
    report = build_speaker_report(words)
    assert report["ranges"][0]["reason"] == "overlapping_turns"
    assert rebuild_segments_by_speaker(words) == [
        {"id": "s1", "word_ids": ["w1"], "speaker": "host"}
    ]


def test_cosine_matching_rejects_low_scores_and_near_ties() -> None:
    assert cosine_similarity([1.0, 0.0], [2.0, 0.0]) == 1.0
    assert match_embedding([1.0, 0.0], {"host": [1.0, 0.0]}, threshold=0.65) == ("host", 1.0)
    assert match_embedding([0.0, 1.0], {"host": [1.0, 0.0]}, threshold=0.65)[0] is None
    tied = {"host": [1.0, 0.0], "guest": [0.99, 0.01]}
    assert match_embedding([1.0, 0.0], tied, threshold=0.65)[0] is None


class _StableEncoder:
    model_id = "fixture-speaker-encoder"

    def encode(self, samples: Sequence[int], sample_rate_hz: int) -> Sequence[float]:
        assert sample_rate_hz == 16000
        return [1.0, 0.0]


class _AlternatingEncoder:
    model_id = "fixture-speaker-encoder"

    def __init__(self) -> None:
        self.calls = 0

    def encode(self, samples: Sequence[int], sample_rate_hz: int) -> Sequence[float]:
        self.calls += 1
        return [1.0, 0.0] if self.calls % 2 else [0.0, 1.0]


def _speech_sample() -> list[int]:
    return [0] * 16000 + [12000] * (16000 * 3)


def test_enrollment_rejects_short_and_inconsistent_samples_and_saves_only_embedding() -> None:
    with pytest.raises(EnrollmentError, match="too short"):
        enroll_samples([100] * 16000, 16000, _StableEncoder())
    with pytest.raises(EnrollmentError, match="multiple speakers") as error:
        enroll_samples(_speech_sample(), 16000, _AlternatingEncoder())
    assert "12000" not in str(error.value)
    result = enroll_samples(_speech_sample(), 16000, _StableEncoder())
    with tempfile.TemporaryDirectory(dir="runs", prefix="speaker-test-") as temporary_dir:
        voices_root = Path(temporary_dir) / "voices"
        path = save_voice_profile("host.json", result, voices_root=voices_root)
        model, vector = read_embedding_profile(path)
        assert model == "fixture-speaker-encoder"
        assert vector == pytest.approx((1.0, 0.0))
        assert "embedding" in path.read_text(encoding="utf-8")
        assert not list(path.parent.glob("*.wav"))
        with pytest.raises(SpeakerError, match="inside the voices directory"):
            save_voice_profile("../escape.json", result, voices_root=voices_root)


def test_unknown_question_answer_and_timeout_remain_explicit() -> None:
    speakers = _speakers()
    ensure_unknown_speaker(speakers, "unknown_1")
    question = make_identify_question("identify_1", "unknown_1", "ask_user/unknown_1.wav", speakers)
    assert question["type"] == "identify_speaker"
    assert question["free_text_allowed"] is True
    assert len(question["candidate_names"]) <= 3
    assert "ask_user/unknown_1.wav" == question["snippet_path"]
    words = _fixture("words", "valid_minimal")
    words["words"][0]["speaker"] = "unknown_1"
    words["words"][0]["speaker_conf"] = 0.2
    diff = apply_identification_answer(speakers, words, "unknown_1", "Host")
    assert diff["speaker_key_after"] == "host"
    assert diff["reassigned_word_count"] == 1
    assert words["words"][0]["speaker_conf"] == 0.2
    assert validate("speakers", speakers) == []
    assert validate("words", words) == []
    timed = {
        "status": "awaiting_user",
        "created_at_epoch": 100.0,
        "questions": [
            {
                "id": "q1",
                "type": "identify_speaker",
                "speaker_key": "unknown_1",
                "status": "pending",
            }
        ],
        "warnings": [],
    }
    assert expire_pending_questions(timed, now_epoch=120.0, timeout_s=30) == []
    warning = expire_pending_questions(timed, now_epoch=131.0, timeout_s=30)
    assert timed["status"] == "timed_out"
    assert "retained Unknown 1" in warning[0]["warning"]


def test_overlap_and_hybrid_are_valid_in_words_contract() -> None:
    words = _fixture("words", "valid_minimal")
    words["speaker_mode"] = "hybrid"
    words["words"][0]["overlap"] = True
    assert validate("words", words) == []


def test_hf_token_shaped_value_is_redacted_and_absent_from_speaker_artifacts() -> None:
    secret = "hf_" + "test-" + "secret-value"
    safe = redact({"hf_token": secret, "message": f"hf_token={secret}"})
    assert secret not in json.dumps(safe)
    artifact = {"speaker_report": build_speaker_report([]), "ask_user": {"questions": []}}
    assert secret not in json.dumps(artifact)


def test_pending_identification_blocks_downstream_stages(tmp_path: Path) -> None:
    words_path = tmp_path / "words.json"
    ask_path = tmp_path / "ask_user.json"
    ask_path.write_text(
        json.dumps(
            {
                "status": "awaiting_user",
                "created_at_epoch": 100.0,
                "timeout_s": 30,
                "questions": [
                    {
                        "id": "identify_1",
                        "type": "identify_speaker",
                        "speaker_key": "unknown_1",
                        "status": "pending",
                    }
                ],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
    assert _has_pending_speaker_question(words_path, now_epoch=120.0)
    assert not _has_pending_speaker_question(words_path, now_epoch=131.0)
    expired = json.loads(ask_path.read_text(encoding="utf-8"))
    assert expired["status"] == "timed_out"
    assert "retained Unknown 1" in expired["warnings"][0]["warning"]
    ask_path.write_text(
        json.dumps(
            {
                "status": "answered",
                "questions": [{"speaker_key": "unknown_1", "status": "answered"}],
            }
        ),
        encoding="utf-8",
    )
    assert not _has_pending_speaker_question(words_path, now_epoch=120.0)


def test_enrollment_cli_does_not_echo_hf_token_or_private_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from argparse import Namespace

    secret = "hf_" + "synthetic-" + "token"
    audio_path = tmp_path / "private-enrollment-sample.wav"
    with wave.open(str(audio_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(struct.pack("<h", 12000) * (16000 * 4))
    monkeypatch.setenv("HF_TOKEN", secret)
    assert task_enroll(Namespace(name="speaker", audio=str(audio_path))) == 1
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert str(audio_path) not in captured.out + captured.err
    assert "no accepted local speaker embedding engine" in captured.err
    assert "HF_TOKEN" not in safe_child_environment({"HF_TOKEN": secret, "PATH": "safe"})


def test_hf_token_shaped_value_is_redacted_from_speaker_artifacts() -> None:
    secret = "hf_" + "test-" + "secret-value"
    safe = redact({"hf_token": secret, "message": f"hf_token={secret}"})
    assert secret not in json.dumps(safe)
    artifact = {"speaker_report": build_speaker_report([]), "ask_user": {"questions": []}}
    assert secret not in json.dumps(artifact)


def test_answer_speaker_cli_persists_only_after_confirmed_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from argparse import Namespace

    root = tmp_path
    job_dir = root / "runs" / "speaker-job"
    job_dir.mkdir(parents=True)
    speakers = _speakers()
    ensure_unknown_speaker(speakers, "unknown_1")
    words = _fixture("words", "valid_minimal")
    words["speaker_mode"] = "single"
    words["words"][0]["speaker"] = "unknown_1"
    words["words"][0]["speaker_conf"] = 0.2
    words["words"][0]["track"] = "audio_0"
    (job_dir / "speakers.json").write_text(json.dumps(speakers), encoding="utf-8")
    (job_dir / "words.json").write_text(json.dumps(words), encoding="utf-8")
    (job_dir / "ask_user.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "status": "awaiting_user",
                "created_at_epoch": time.time(),
                "timeout_s": 86400,
                "questions": [
                    {
                        "id": "identify_speaker_1",
                        "type": "identify_speaker",
                        "speaker_key": "unknown_1",
                        "snippet_path": "ask_user/unknown_1.wav",
                        "candidate_names": ["Host"],
                        "free_text_allowed": True,
                        "status": "pending",
                    }
                ],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(tasks, "ROOT", root)
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")

    assert (
        task_answer_speaker(
            Namespace(job_dir="runs/speaker-job", speaker_key="unknown_1", name="Host")
        )
        == 0
    )
    capsys.readouterr()
    updated_words = json.loads((job_dir / "words.json").read_text(encoding="utf-8"))
    updated_speakers = json.loads((job_dir / "speakers.json").read_text(encoding="utf-8"))
    updated_question = json.loads((job_dir / "ask_user.json").read_text(encoding="utf-8"))
    persisted_speakers = json.loads((root / "speakers.json").read_text(encoding="utf-8"))
    assert updated_words["words"][0]["speaker"] == "host"
    assert updated_words["words"][0]["speaker_conf"] == 0.2
    assert "unknown_1" not in updated_speakers["speakers"]
    assert updated_question["status"] == "answered"
    assert persisted_speakers == updated_speakers
