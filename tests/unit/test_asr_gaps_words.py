from __future__ import annotations

import wave
from pathlib import Path
from types import SimpleNamespace

from orchestrator.contracts import validate
from perception.asr import (
    AsrResult,
    AsrWord,
    FakeAsrEngine,
    WhisperXConfig,
    WhisperXEngine,
    _words_from_segments,
)
from perception.gaps import GapThresholds, refine_gaps
from perception.words import build_words_document


def _tone_silence(path: Path) -> None:
    import math
    import struct

    values: list[int] = []
    for sample_index in range(32000):
        if sample_index < 6400 or sample_index >= 12800:
            value = int(8000 * math.sin(sample_index * 2 * math.pi * 440 / 16000))
        else:
            value = 0
        values.append(value)
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"".join(struct.pack("<h", value) for value in values))


def _result() -> AsrResult:
    return AsrResult(
        words=(
            AsrWord("start", 0.2, 0.4, 0.9, True, 0),
            AsrWord("pause", 0.8, 1.0, 0.8, True, 1),
            AsrWord("unresolved", None, None, 0.0, False, 1),
        ),
        detected_language="en",
        language_confidence=0.97,
        model="small",
        align_model="fixture-aligner",
        params_hash="fixture-hash",
        device="cpu",
        compute_type="int8",
    )


def test_alignment_mismatch_marks_segment_unaligned_without_times() -> None:
    words = _words_from_segments(
        [{"text": "hello world"}],
        [{"words": [{"word": "unrelated", "start": 0.0, "end": 0.2}]}],
    )
    assert [word.text for word in words] == ["hello", "world"]
    assert all(not word.aligned and word.start is None and word.end is None for word in words)


def test_fake_asr_fixture_is_deterministic() -> None:
    fixture = Path(__file__).parents[1] / "data" / "fake_asr.json"
    result = FakeAsrEngine.from_fixture(fixture).transcribe_aligned("ignored.wav")
    assert result.detected_language == "en"
    assert result.engine == "fixture"
    assert result.words[1].aligned is False
    assert result.words[1].start is None


def test_noise_floor_refines_gap_and_words_contract_records_both_bounds(tmp_path: Path) -> None:
    audio = tmp_path / "tone-silence.wav"
    _tone_silence(audio)
    result = _result()
    gaps = refine_gaps(result, audio, GapThresholds(minimum_gap_ms=250))
    assert len(gaps) == 1
    assert gaps[0].energy_start is not None
    assert gaps[0].energy_end is not None
    document = build_words_document(
        result,
        str(audio),
        "sha256:" + "a" * 64,
        "30000/1001",
    )
    issues = validate("words", document)
    assert not issues
    assert document["words"][2]["start"] is None
    assert document["words"][2]["alignment_status"] == "unaligned"
    assert document["gaps"][0]["refinement"]["asr_start"] == 0.4
    assert document["gaps"][0]["refinement"]["energy_start"] is not None


def test_whisperx_loader_uses_supported_api_and_alignment_failure_is_flagged() -> None:
    load_calls: list[dict[str, object]] = []

    class Model:
        def transcribe(self, audio: object, *, batch_size: int, language: str) -> dict[str, object]:
            del audio, batch_size, language
            return {"language": "en", "segments": [{"text": "test words"}]}

    def load_model(*args: object, **kwargs: object) -> Model:
        del args
        load_calls.append(kwargs)
        return Model()

    fake_whisperx = SimpleNamespace(
        load_model=load_model,
        load_audio=lambda _path: object(),
        load_align_model=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("not aligned")),
    )
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    engine = WhisperXEngine(WhisperXConfig(device="cpu", language="en"))
    engine._imports = lambda: (fake_torch, fake_whisperx)  # type: ignore[method-assign]
    audio = Path("fake.wav")
    audio.touch()
    try:
        result = engine.transcribe_aligned(audio)
    finally:
        audio.unlink()
    assert "batch_size" not in load_calls[0]
    assert len(result.words) == 2
    assert all(not word.aligned and word.start is None for word in result.words)


def test_edl_rejects_unaligned_word_reference() -> None:
    from orchestrator.contracts import check_edl_against
    from orchestrator.contracts.hashing import hash_words

    words = {
        "schema_version": "2.0.0",
        "source_hash": "sha256:" + "b" * 64,
        "fps": "30000/1001",
        "asr": {
            "engine": "fixture",
            "model": "small",
            "align_model": "none",
            "params_hash": "test",
        },
        "speaker_mode": "single",
        "words": [
            {
                "id": "w1",
                "text": "maybe",
                "start": None,
                "end": None,
                "alignment_status": "unaligned",
                "speaker": None,
                "speaker_conf": 0,
                "word_conf": 0,
            }
        ],
        "segments": [{"id": "s1", "word_ids": ["w1"]}],
        "gaps": [],
        "audio_events": [],
    }
    edl = {
        "words_hash": hash_words(words),
        "cuts": [{"id": "c1", "remove": {"from_word": "w1", "to_word": "w1"}}],
    }
    issues = check_edl_against(
        edl,
        words,
        {"speakers": {}},
        {"transitions": [], "video_fx": [], "audio_fx": [], "text_presets": [], "sfx": []},
    )
    assert any(issue.code.value == "E_WORD_UNALIGNED" for issue in issues)


def test_unaligned_word_breaks_gap_adjacency(tmp_path: Path) -> None:
    audio = tmp_path / "tone-silence.wav"
    _tone_silence(audio)
    base = _result()
    result = AsrResult(
        words=(base.words[0], base.words[2], base.words[1]),
        detected_language="en",
        language_confidence=None,
        model="small",
        align_model="fixture-aligner",
        params_hash="fixture",
        device="cpu",
        compute_type="int8",
    )
    assert refine_gaps(result, audio) == ()


def test_flat_audio_is_not_mislabeled_as_silence(tmp_path: Path) -> None:
    import struct

    audio = tmp_path / "flat-tone.wav"
    with wave.open(str(audio), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"".join(struct.pack("<h", 4000) for _ in range(32000)))
    gaps = refine_gaps(_result(), audio)
    assert len(gaps) == 1
    assert gaps[0].energy_start is None
    assert gaps[0].energy_end is None
