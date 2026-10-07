from __future__ import annotations

import json
import math
import shutil
import wave
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from orchestrator import sfx
from orchestrator.sfx import SfxIndexError, index_sfx_directory, search_sfx


def _write_tone(path: Path, *, sample_rate: int = 48000, duration_seconds: int = 1) -> None:
    """Create a deterministic -20 dBFS 1 kHz PCM tone without external tools."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(
        int(3276 * math.sin(2 * math.pi * 1000 * index / sample_rate)).to_bytes(
            2, "little", signed=True
        )
        for index in range(sample_rate * duration_seconds)
    )
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(frames)


def _measurement(_path: Path) -> dict[str, float | int]:
    return {
        "duration": 0.1,
        "sample_rate": 48000,
        "loudness_lufs": -23.0,
        "peak_dbfs": -20.0,
    }


def test_sfx_index_is_stable_and_unlicensed_entries_are_disabled(tmp_path: Path) -> None:
    licensed = tmp_path / "licensed" / "soft_whoosh.wav"
    unlicensed = tmp_path / "unlicensed" / "soft_whoosh.wav"
    _write_tone(licensed)
    _write_tone(unlicensed)
    licensed.with_suffix(".json").write_text(
        json.dumps({"license": "CC0-1.0", "source": "test fixture", "tags": ["whoosh", "soft"]}),
        encoding="utf-8",
    )

    first, warnings = index_sfx_directory(tmp_path, measure=_measurement)
    second, _ = index_sfx_directory(tmp_path, measure=_measurement)

    assert warnings == ["SFX entry without license metadata is disabled"]
    assert [row["key"] for row in first["entries"]] == [row["key"] for row in second["entries"]]
    assert first["entries"][0]["enabled"] is True
    assert first["entries"][1]["enabled"] is False
    assert first["entries"][0]["sample_rate"] == 48000
    assert first["entries"][0]["fingerprint"]


def test_sfx_search_returns_only_enabled_keyword_and_tag_matches(tmp_path: Path) -> None:
    audio = tmp_path / "whoosh.wav"
    _write_tone(audio)
    audio.with_suffix(".json").write_text(
        json.dumps({"license": "CC0-1.0", "tags": ["whoosh", "topic_change"]}),
        encoding="utf-8",
    )
    index, _ = index_sfx_directory(tmp_path, measure=_measurement)

    assert search_sfx(index, query="topic", tags={"whoosh"}) == [index["entries"][0]["key"]]
    assert search_sfx(index, query="impact") == []


def test_sfx_index_rejects_unsafe_sidecar_tags(tmp_path: Path) -> None:
    audio = tmp_path / "whoosh.wav"
    _write_tone(audio)
    audio.with_suffix(".json").write_text(
        json.dumps({"license": "CC0-1.0", "tags": ["../private"]}),
        encoding="utf-8",
    )

    with pytest.raises(SfxIndexError, match="safe tokens"):
        index_sfx_directory(tmp_path, measure=_measurement)


def test_sfx_index_skips_unsupported_extensions(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not audio", encoding="utf-8")

    index, warnings = index_sfx_directory(tmp_path, measure=_measurement)

    assert index["entries"] == []
    assert warnings == ["unsupported file extension was skipped"]


def test_ffmpeg_measurement_parser_extracts_integrated_loudness_and_peak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "tone.wav"
    _write_tone(audio)
    outputs = iter(
        [
            CompletedProcess(
                [],
                0,
                '{"streams":[{"sample_rate":"48000","codec_name":"pcm_s16le"}],'
                '"format":{"duration":"0.1","format_name":"wav"}}',
                "",
            ),
            CompletedProcess(
                [],
                0,
                "",
                (
                    "Integrated loudness:\\n"
                    "  I:         -23.0 LUFS\\n"
                    "True peak:\\n"
                    "  Peak:      -20.0 dBFS\\n"
                ),
            ),
        ]
    )
    monkeypatch.setattr(sfx, "_run", lambda _command: next(outputs))

    measured = sfx._ffprobe_measure(audio)

    assert measured == {
        "duration": 0.1,
        "sample_rate": 48000,
        "loudness_lufs": -23.0,
        "peak_dbfs": -20.0,
    }


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="local FFmpeg tools are unavailable",
)
def test_real_ffmpeg_measures_a_generated_tone_within_tolerance(tmp_path: Path) -> None:
    audio = tmp_path / "known_tone.wav"
    _write_tone(audio, duration_seconds=5)
    audio.with_suffix(".json").write_text(
        json.dumps({"license": "TEST-ONLY", "tags": ["tone"]}),
        encoding="utf-8",
    )

    index, _ = index_sfx_directory(tmp_path)
    measured = index["entries"][0]

    assert measured["loudness_lufs"] == pytest.approx(-23.0, abs=1.0)
    assert measured["peak_dbfs"] == pytest.approx(-20.0, abs=1.0)
