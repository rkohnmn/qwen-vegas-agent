"""ffmpeg-based reference audio renderer for compiled keep ranges."""

from __future__ import annotations

import subprocess
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .childenv import safe_child_environment
from .compiler import FrameInterval, kept_intervals


class RenderError(RuntimeError):
    """Safe reference-render failure without command output or paths."""


@dataclass(frozen=True, slots=True)
class RenderResult:
    output: Path
    sample_rate: int
    join_samples: tuple[int, ...]
    fade_samples: int


def _nearest(value: Fraction) -> int:
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def render_cut_audio(
    ffmpeg: str,
    source_wav: str | Path,
    output_wav: str | Path,
    fps: str,
    duration_frames: int,
    removed: Sequence[FrameInterval],
    *,
    fade_ms: int = 20,
    sample_rate: int = 16000,
) -> RenderResult:
    source = Path(source_wav)
    output = Path(output_wav)
    try:
        with wave.open(str(source), "rb") as wav:
            if (
                wav.getframerate() != sample_rate
                or wav.getnchannels() != 1
                or wav.getsampwidth() != 2
            ):
                raise RenderError("reference renderer requires 16 kHz mono PCM16 audio")
            input_samples = wav.getnframes()
    except (OSError, wave.Error):
        raise RenderError("normalized audio could not be opened") from None
    rate = Fraction(fps)
    preserved = kept_intervals(duration_frames, list(removed))
    sample_ranges: list[tuple[int, int]] = []
    for start_frame, end_frame in preserved:
        start_sample = _nearest(Fraction(start_frame * sample_rate, 1) / rate)
        end_sample = _nearest(Fraction(end_frame * sample_rate, 1) / rate)
        start_sample = min(max(0, start_sample), input_samples)
        end_sample = min(max(start_sample, end_sample), input_samples)
        if end_sample > start_sample:
            sample_ranges.append((start_sample, end_sample))
    if not sample_ranges:
        raise RenderError("edit leaves no audio to render")
    fade_samples = max(0, round(sample_rate * max(0, fade_ms) / 1000))
    filters: list[str] = []
    raw_labels = "".join(f"[raw{index}]" for index in range(len(sample_ranges)))
    filters.append(f"[0:a]asplit={len(sample_ranges)}{raw_labels}")
    for index, (start, end) in enumerate(sample_ranges):
        filters.append(
            f"[raw{index}]atrim=start_sample={start}:end_sample={end},"
            f"asetpts=PTS-STARTPTS[s{index}]"
        )
    joins: list[int] = []
    output_length = sample_ranges[0][1] - sample_ranges[0][0]
    current_label = "s0"
    for index in range(1, len(sample_ranges)):
        next_length = sample_ranges[index][1] - sample_ranges[index][0]
        actual_fade = min(fade_samples, output_length // 2, next_length // 2)
        joins.append(max(0, output_length - actual_fade // 2))
        next_label = f"mix{index}"
        if actual_fade:
            filters.append(
                f"[{current_label}][s{index}]acrossfade="
                f"d={actual_fade / sample_rate:.6f}:c1=tri:c2=tri[{next_label}]"
            )
        else:
            filters.append(f"[{current_label}][s{index}]concat=n=2:v=0:a=1[{next_label}]")
        output_length += next_length - actual_fade
        current_label = next_label
    args = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{current_label}]",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            env=safe_child_environment(),
        )
    except OSError:
        raise RenderError("ffmpeg could not be started") from None
    if completed.returncode != 0 or not output.is_file():
        raise RenderError("ffmpeg reference render failed")
    return RenderResult(output, sample_rate, tuple(joins), fade_samples)
