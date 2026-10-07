from __future__ import annotations

import wave
from pathlib import Path
from types import SimpleNamespace

from orchestrator.contracts import validate
from orchestrator.metrics import real_time_factor
from perception.asr import (
    AsrResult,
    AsrWord,
    FakeAsrEngine,
    WhisperXConfig,
    WhisperXEngine,
    _alignment_model_name,
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


def test_sentence_split_alignment_maps_back_to_raw_segment_indices() -> None:
    words = _words_from_segments(
        [
            {"text": "hello world. next time"},
            {"text": "good bye"},
        ],
        [
            {
                "text": "hello world.",
                "words": [
                    {"word": "hello", "start": 0.0, "end": 0.2},
                    {"word": "world.", "start": 0.2, "end": 0.4},
                ],
            },
            {
                "text": "next time",
                "words": [
                    {"word": "next", "start": 0.5, "end": 0.7},
                    {"word": "time", "start": 0.7, "end": 0.9},
                ],
            },
            {"text": "good bye", "words": []},
        ],
    )

    assert [word.text for word in words] == [
        "hello",
        "world.",
        "next",
        "time",
        "good",
        "bye",
    ]
    assert [word.segment_index for word in words] == [0, 0, 0, 0, 1, 1]
    assert [word.aligned for word in words] == [True, True, True, True, False, False]
    assert words[2].start == 0.5
    assert words[-1].start is None and words[-1].end is None


def test_sentence_alignment_text_mismatch_falls_back_to_unaligned_raw_words() -> None:
    words = _words_from_segments(
        [{"text": "hello there"}],
        [
            {
                "text": "unrelated words",
                "words": [
                    {"word": "unrelated", "start": 0.0, "end": 0.2},
                    {"word": "words", "start": 0.2, "end": 0.4},
                ],
            }
        ],
    )

    assert [word.text for word in words] == ["hello", "there"]
    assert all(not word.aligned and word.start is None for word in words)


def test_finer_japanese_subword_alignment_is_not_promoted_to_word_timing() -> None:
    words = _words_from_segments(
        [{"text": "こんにちは世界"}],
        [
            {
                "words": [
                    {"word": "こんにちは", "start": 0.0, "end": 0.3},
                    {"word": "世界", "start": 0.3, "end": 0.5},
                ]
            }
        ],
    )
    assert len(words) == 1
    assert words[0].aligned is False
    assert words[0].start is None and words[0].end is None


def test_alignment_model_name_uses_language_checkpoint_id() -> None:
    assert (
        _alignment_model_name(
            "ja",
            {"type": "huggingface"},
            {"ja": "jonatasgrosman/wav2vec2-large-xlsr-53-japanese"},
        )
        == "jonatasgrosman/wav2vec2-large-xlsr-53-japanese"
    )
    assert _alignment_model_name("en", {"model_name": "specific/model"}, {}) == "specific/model"


def test_real_time_factor_is_elapsed_over_media_duration() -> None:
    assert real_time_factor(30.0, 60.0) == 0.5
    assert real_time_factor(0.0, 60.0) is None
    assert real_time_factor(30.0, 0.0) is None


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


def test_faster_whisper_loader_avoids_vad_and_alignment_failure_is_flagged() -> None:
    load_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    transcribe_calls: list[dict[str, object]] = []

    class Segment:
        text = "test words"
        start = 0.0
        end = 0.4

    class Model:
        def transcribe(self, audio: object, **kwargs: object) -> tuple[object, object]:
            transcribe_calls.append({"audio": audio, **kwargs})
            info = SimpleNamespace(language="en", language_probability=0.97)
            return iter([Segment()]), info

    def load_model(*args: object, **kwargs: object) -> Model:
        load_calls.append((args, kwargs))
        return Model()

    normalized_audio = object()
    fake_whisperx = SimpleNamespace(
        load_audio=lambda _path: normalized_audio,
        load_align_model=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("not aligned")),
    )
    fake_faster_whisper = SimpleNamespace(WhisperModel=load_model)
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    engine = WhisperXEngine(WhisperXConfig(device="cpu"))
    engine._imports = lambda: (fake_torch, fake_whisperx, fake_faster_whisper)  # type: ignore[method-assign]
    audio = Path("fake.wav")
    audio.touch()
    try:
        result = engine.transcribe_aligned(audio)
    finally:
        audio.unlink()

    assert load_calls[0][0][0] == "small"
    assert load_calls[0][1]["compute_type"] == "int8"
    assert transcribe_calls[0]["audio"] is normalized_audio
    assert transcribe_calls[0]["language"] is None
    assert transcribe_calls[0]["vad_filter"] is False
    assert transcribe_calls[0]["word_timestamps"] is False
    assert result.detected_language == "en"
    assert result.language_confidence == 0.97
    assert result.align_model == "unavailable"
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
