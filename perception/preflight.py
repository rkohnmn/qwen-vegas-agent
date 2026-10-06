"""Read-only media inspection through ffprobe with bounded argument-list calls."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Any

from orchestrator.childenv import safe_child_environment


class MediaToolError(RuntimeError):
    """Safe, typed failure from the external media tool."""


class WarningCode(StrEnum):
    VFR = "W_VFR"
    UNSUPPORTED_CONTAINER_RISK = "W_UNSUPPORTED_CONTAINER_RISK"
    HEVC_RISK = "W_HEVC_RISK"
    MULTI_AUDIO = "W_MULTI_AUDIO"
    NO_AUDIO = "W_NO_AUDIO"
    NO_VIDEO = "W_NO_VIDEO"
    ODD_SAMPLE_RATE = "W_ODD_SAMPLE_RATE"
    FPS_UNDETERMINED = "W_FPS_UNDETERMINED"
    VFR_SAMPLE_INSUFFICIENT = "W_VFR_SAMPLE_INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class MediaWarning:
    code: WarningCode
    message: str


@dataclass(frozen=True, slots=True)
class StreamInfo:
    index: int
    kind: str
    codec: str | None
    profile: str | None
    duration: Fraction | None
    frame_rate: Fraction | None
    real_frame_rate: Fraction | None
    sample_rate: int | None
    channels: int | None
    channel_layout: str | None
    width: int | None
    height: int | None


@dataclass(frozen=True, slots=True)
class MediaProbe:
    container_names: tuple[str, ...]
    duration: Fraction | None
    streams: tuple[StreamInfo, ...]
    frame_rate: Fraction | None
    real_frame_rate: Fraction | None
    vfr_detected: bool | None
    sampled_frame_timestamps: tuple[Fraction, ...]
    warnings: tuple[MediaWarning, ...]

    @property
    def audio_streams(self) -> tuple[StreamInfo, ...]:
        return tuple(stream for stream in self.streams if stream.kind == "audio")

    @property
    def video_streams(self) -> tuple[StreamInfo, ...]:
        return tuple(stream for stream in self.streams if stream.kind == "video")


def _positive_fraction(value: object, *, allow_zero: bool = False) -> Fraction | None:
    if not isinstance(value, str | int) or isinstance(value, bool):
        return None
    try:
        result = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None
    return result if result > 0 or (allow_zero and result == 0) else None


def _optional_int(value: object) -> int | None:
    if not isinstance(value, str | int) or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except ValueError:
        return None
    return result if result >= 0 else None


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _run_json(args: list[str], executable: str, timeout_s: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            check=False,
            shell=False,
            text=True,
            timeout=timeout_s,
            env=safe_child_environment(),
        )
    except FileNotFoundError:
        raise MediaToolError("ffprobe is not installed or not available on PATH") from None
    except subprocess.TimeoutExpired:
        raise MediaToolError("ffprobe inspection timed out") from None
    except OSError:
        raise MediaToolError("ffprobe could not be started") from None
    if result.returncode:
        raise MediaToolError("ffprobe could not inspect the selected media")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise MediaToolError("ffprobe returned invalid metadata") from None
    if not isinstance(data, dict):
        raise MediaToolError("ffprobe returned invalid metadata")
    return data


def _stream(row: dict[str, Any]) -> StreamInfo | None:
    index = _optional_int(row.get("index"))
    kind = row.get("codec_type")
    if index is None or kind not in ("audio", "video"):
        return None
    return StreamInfo(
        index=index,
        kind=kind,
        codec=row.get("codec_name") if isinstance(row.get("codec_name"), str) else None,
        profile=row.get("profile") if isinstance(row.get("profile"), str) else None,
        duration=_positive_fraction(row.get("duration")),
        frame_rate=_positive_fraction(row.get("avg_frame_rate")),
        real_frame_rate=_positive_fraction(row.get("r_frame_rate")),
        sample_rate=_optional_int(row.get("sample_rate")),
        channels=_optional_int(row.get("channels")),
        channel_layout=row.get("channel_layout")
        if isinstance(row.get("channel_layout"), str)
        else None,
        width=_optional_int(row.get("width")),
        height=_optional_int(row.get("height")),
    )


def _timestamps(data: dict[str, Any]) -> tuple[Fraction, ...]:
    rows = data.get("frames", [])
    if not isinstance(rows, list):
        return ()
    result: list[Fraction] = []
    for item in rows:
        frame = _dict(item)
        stamp = _positive_fraction(
            frame.get("best_effort_timestamp_time", frame.get("pkt_pts_time")),
            allow_zero=True,
        )
        if stamp is not None and (not result or stamp > result[-1]):
            result.append(stamp)
    return tuple(result)


def _intervals_vary(timestamps: tuple[Fraction, ...]) -> bool | None:
    intervals = [b - a for a, b in zip(timestamps, timestamps[1:], strict=False)]
    if len(intervals) < 2:
        return None
    median = sorted(intervals)[len(intervals) // 2]
    tolerance = max(median / 50, Fraction(1, 1000))
    return any(abs(value - median) > tolerance for value in intervals)


def probe_media(
    media_path: str | Path,
    *,
    ffprobe_executable: str = "ffprobe",
    sample_packet_count: int = 96,
    timeout_s: int = 30,
) -> MediaProbe:
    """Inspect container, streams, rational rates, and bounded frame timestamps."""
    path = Path(media_path)
    if not path.is_file():
        raise MediaToolError("selected media file does not exist")
    if not 3 <= sample_packet_count <= 10000:
        raise ValueError("sample_packet_count must be between 3 and 10000")
    if not 1 <= timeout_s <= 600:
        raise ValueError("timeout_s must be between 1 and 600")
    executable = shutil.which(ffprobe_executable)
    if executable is None:
        raise MediaToolError("ffprobe is not installed or not available on PATH")
    metadata = _run_json(
        [
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-show_entries",
            (
                "format=format_name,duration:stream=index,codec_type,codec_name,profile,width,height,"
                "avg_frame_rate,r_frame_rate,duration,sample_rate,channels,channel_layout"
            ),
            "-of",
            "json",
            str(path),
        ],
        executable,
        timeout_s,
    )
    format_data = _dict(metadata.get("format"))
    raw_streams = metadata.get("streams", [])
    if not isinstance(raw_streams, list):
        raise MediaToolError("ffprobe returned invalid stream metadata")
    streams = tuple(stream for item in raw_streams if (stream := _stream(_dict(item))) is not None)
    videos = tuple(stream for stream in streams if stream.kind == "video")
    audios = tuple(stream for stream in streams if stream.kind == "audio")
    container_value = format_data.get("format_name")
    containers = (
        tuple(part.strip() for part in container_value.split(",") if part.strip())
        if isinstance(container_value, str)
        else ()
    )
    duration = _positive_fraction(format_data.get("duration"))
    if duration is None:
        duration = max((s.duration for s in streams if s.duration is not None), default=None)
    fps = videos[0].frame_rate if videos else None
    real_fps = videos[0].real_frame_rate if videos else None

    timestamps: tuple[Fraction, ...] = ()
    sampled_vfr: bool | None = None
    if videos:
        frames = _run_json(
            [
                "-v",
                "error",
                "-select_streams",
                str(videos[0].index),
                "-read_intervals",
                f"%+#{sample_packet_count}",
                "-show_frames",
                "-show_entries",
                "frame=best_effort_timestamp_time,pkt_pts_time",
                "-of",
                "json",
                str(path),
            ],
            executable,
            timeout_s,
        )
        timestamps = _timestamps(frames)
        sampled_vfr = _intervals_vary(timestamps)
    rates_differ = (
        fps is not None and real_fps is not None and abs(fps - real_fps) > Fraction(1, 1000)
    )
    if rates_differ or sampled_vfr is True:
        vfr: bool | None = True
    elif sampled_vfr is False:
        vfr = False
    else:
        vfr = None

    warnings: list[MediaWarning] = []
    if vfr:
        warnings.append(
            MediaWarning(WarningCode.VFR, "reported rates or sampled timestamps indicate VFR")
        )
    if not videos:
        warnings.append(MediaWarning(WarningCode.NO_VIDEO, "no video stream was found"))
    if not audios:
        warnings.append(MediaWarning(WarningCode.NO_AUDIO, "no audio stream was found"))
    if len(audios) > 1:
        warnings.append(MediaWarning(WarningCode.MULTI_AUDIO, "multiple audio streams were found"))
    if {"matroska", "mkv", "webm"}.intersection(containers):
        warnings.append(
            MediaWarning(
                WarningCode.UNSUPPORTED_CONTAINER_RISK,
                "container may need remuxing for older VEGAS decoders",
            )
        )
    if any(s.codec == "hevc" for s in videos):
        warnings.append(
            MediaWarning(WarningCode.HEVC_RISK, "HEVC may not import cleanly in older VEGAS builds")
        )
    if any(s.sample_rate not in (None, 44100, 48000) for s in audios):
        warnings.append(
            MediaWarning(WarningCode.ODD_SAMPLE_RATE, "audio uses an uncommon sample rate")
        )
    if videos and fps is None:
        warnings.append(
            MediaWarning(WarningCode.FPS_UNDETERMINED, "video frame rate was not reported")
        )
    if videos and len(timestamps) < 3 and sampled_vfr is None:
        warnings.append(
            MediaWarning(
                WarningCode.VFR_SAMPLE_INSUFFICIENT,
                "fewer than three frame timestamps were available for VFR sampling",
            )
        )
    return MediaProbe(
        container_names=containers,
        duration=duration,
        streams=streams,
        frame_rate=fps,
        real_frame_rate=real_fps,
        vfr_detected=vfr,
        sampled_frame_timestamps=timestamps,
        warnings=tuple(warnings),
    )
