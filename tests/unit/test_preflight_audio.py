from __future__ import annotations

import json
import subprocess
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from perception import audio, preflight


def completed(stdout: str, *, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["fake"], returncode=returncode, stdout=stdout, stderr=""
    )


def test_preflight_uses_argument_lists_and_reports_media_risks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "clip with spaces $(literal).mkv"
    media.write_bytes(b"read-only sentinel")
    calls: list[tuple[list[str], dict[str, Any]]] = []
    metadata = {
        "format": {"format_name": "matroska,webm", "duration": "4.000"},
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "hevc",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30000/1001",
                "r_frame_rate": "30/1",
                "duration": "4.000",
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "32000",
                "channels": 2,
            },
            {
                "index": 2,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
            },
        ],
    }
    frames = {
        "frames": [
            {"best_effort_timestamp_time": str(stamp)}
            for stamp in ("0", "0.033", "0.067", "0.133", "0.167")
        ]
    }
    responses = iter((metadata, frames))

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return completed(json.dumps(next(responses)))

    monkeypatch.setattr(preflight.shutil, "which", lambda _: "ffprobe.exe")
    monkeypatch.setattr(preflight.subprocess, "run", fake_run)

    result = preflight.probe_media(media, sample_packet_count=64)

    assert result.duration == Fraction(4)
    assert result.frame_rate == Fraction(30000, 1001)
    assert result.real_frame_rate == Fraction(30, 1)
    assert result.vfr_detected is True
    assert len(result.audio_streams) == 2
    assert result.video_streams[0].codec == "hevc"
    assert {warning.code for warning in result.warnings} == {
        preflight.WarningCode.VFR,
        preflight.WarningCode.UNSUPPORTED_CONTAINER_RISK,
        preflight.WarningCode.HEVC_RISK,
        preflight.WarningCode.MULTI_AUDIO,
        preflight.WarningCode.ODD_SAMPLE_RATE,
    }
    assert all(kwargs["shell"] is False for _, kwargs in calls)
    assert all(args[-1] == str(media) for args, _ in calls)
    assert any("$(literal)" in args[-1] for args, _ in calls)
    assert any("%+#64" in args for args, _ in calls)
    assert media.read_bytes() == b"read-only sentinel"


def test_preflight_identifies_constant_rational_frame_intervals() -> None:
    fps = Fraction(30000, 1001)
    stamps = tuple(Fraction(index, 1) / fps for index in range(5))

    assert preflight._intervals_vary(stamps) is False
    assert preflight._intervals_vary(stamps[:2]) is None


def test_preflight_warns_when_audio_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "silent.mp4"
    media.write_bytes(b"fixture")
    metadata = {
        "format": {"format_name": "mov,mp4", "duration": "2"},
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "avg_frame_rate": "24/1",
                "r_frame_rate": "24/1",
                "duration": "2",
            }
        ],
    }
    frames = {"frames": [{"best_effort_timestamp_time": str(i / 24)} for i in range(5)]}
    responses = iter((metadata, frames))
    monkeypatch.setattr(preflight.shutil, "which", lambda _: "ffprobe")
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *_args, **_kwargs: completed(json.dumps(next(responses))),
    )

    result = preflight.probe_media(media)

    assert result.vfr_detected is False
    assert preflight.WarningCode.NO_AUDIO in {warning.code for warning in result.warnings}


def test_preflight_missing_binary_fails_with_safe_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fixture")
    monkeypatch.setattr(preflight.shutil, "which", lambda _: None)

    with pytest.raises(preflight.MediaToolError, match="not installed"):
        preflight.probe_media(media)


def test_extract_audio_uses_stream_specific_cache_and_never_shells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source $(literal).mp4"
    source.write_bytes(b"read-only source")
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        target = Path(args[-1])
        with wave.open(str(target), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x00\x00" * 160)
        return completed("")

    monkeypatch.setattr(audio.shutil, "which", lambda _: "ffmpeg.exe")
    monkeypatch.setattr(audio.subprocess, "run", fake_run)

    first = audio.extract_audio_stream(source, 3, tmp_path / "cache")
    second = audio.extract_audio_stream(source, 3, tmp_path / "cache")

    assert first.path == second.path
    assert first.cache_key == second.cache_key
    assert first.sample_count == 160
    samples, sample_rate = audio.read_pcm16_mono(first.path)
    assert len(samples) == 160
    assert sample_rate == 16000
    assert len(calls) == 1
    assert calls[0][0][calls[0][0].index("-map") + 1] == "0:3"
    assert calls[0][0][calls[0][0].index("-ar") + 1] == "16000"
    assert calls[0][1]["shell"] is False
    assert str(source) in calls[0][0]
    assert source.read_bytes() == b"read-only source"


def test_extract_audio_fails_cleanly_without_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"read-only source")
    monkeypatch.setattr(audio.shutil, "which", lambda _: None)

    with pytest.raises(audio.AudioExtractionError, match="ffmpeg is not installed"):
        audio.extract_audio_stream(source, 0, tmp_path / "cache")

    assert source.read_bytes() == b"read-only source"
