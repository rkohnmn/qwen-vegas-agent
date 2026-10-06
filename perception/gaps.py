"""Noise-floor-relative silence gap refinement for normalized PCM WAV audio."""

from __future__ import annotations

import math
import statistics
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .asr import AsrResult


@dataclass(frozen=True, slots=True)
class GapThresholds:
    minimum_gap_ms: int = 250
    window_ms: int = 10
    noise_floor_multiplier: float = 2.5
    absolute_rms_floor: float = 0.002
    minimum_quiet_ms: int = 40


@dataclass(frozen=True, slots=True)
class RefinedGap:
    start: float
    end: float
    asr_start: float
    asr_end: float
    energy_start: float | None
    energy_end: float | None
    noise_floor_rms: float
    threshold_rms: float

    def as_dict(self, gap_id: str) -> dict[str, Any]:
        return {
            "id": gap_id,
            "start": self.start,
            "end": self.end,
            "refinement": {
                "asr_start": self.asr_start,
                "asr_end": self.asr_end,
                "energy_start": self.energy_start,
                "energy_end": self.energy_end,
                "noise_floor_rms": self.noise_floor_rms,
                "threshold_rms": self.threshold_rms,
                "method": "pcm_rms_noise_floor",
            },
        }


def _read_windows(path: str | Path, window_ms: int) -> tuple[int, int, list[float]]:
    if window_ms < 1:
        raise ValueError("window_ms must be positive")
    try:
        with wave.open(str(path), "rb") as source:
            rate = source.getframerate()
            channels = source.getnchannels()
            width = source.getsampwidth()
            if rate != 16000 or channels != 1 or width != 2:
                raise ValueError("audio must be 16 kHz mono PCM16 WAV")
            samples_per_window = max(1, rate * window_ms // 1000)
            values: list[float] = []
            while True:
                raw = source.readframes(samples_per_window)
                if not raw:
                    break
                samples = array("h")
                samples.frombytes(raw[: len(raw) - len(raw) % 2])
                if not samples:
                    continue
                squares = sum(sample * sample for sample in samples) / len(samples)
                values.append(math.sqrt(squares) / 32768.0)
            return rate, samples_per_window, values
    except (OSError, wave.Error) as error:
        raise ValueError("normalized audio could not be analyzed") from error


def refine_gaps(
    result: AsrResult,
    audio_path: str | Path,
    thresholds: GapThresholds | None = None,
) -> tuple[RefinedGap, ...]:
    """Refine ASR inter-word spaces to measured quiet windows; record source bounds."""
    limits = thresholds or GapThresholds()
    rate, samples_per_window, energies = _read_windows(audio_path, limits.window_ms)
    if not energies:
        return ()
    ordered_energies = sorted(energies)
    noise_floor = ordered_energies[max(0, int(len(ordered_energies) * 0.2))]
    median_energy = statistics.median(ordered_energies)
    relative_threshold = min(
        noise_floor * limits.noise_floor_multiplier,
        median_energy * 0.5,
    )
    threshold = max(limits.absolute_rms_floor, relative_threshold)
    gaps: list[RefinedGap] = []
    minimum_gap = limits.minimum_gap_ms / 1000.0
    minimum_quiet_windows = max(1, math.ceil(limits.minimum_quiet_ms / limits.window_ms))
    for left, right in zip(result.words, result.words[1:], strict=False):
        if not left.aligned or not right.aligned or left.end is None or right.start is None:
            continue
        asr_start = float(left.end)
        asr_end = float(right.start)
        if asr_end - asr_start < minimum_gap:
            continue
        first = max(0, int(asr_start * rate // samples_per_window))
        last = min(len(energies), math.ceil(asr_end * rate / samples_per_window))
        quiet_runs: list[tuple[int, int]] = []
        run_start: int | None = None
        for index in range(first, last):
            if energies[index] <= threshold:
                if run_start is None:
                    run_start = index
            elif run_start is not None:
                if index - run_start >= minimum_quiet_windows:
                    quiet_runs.append((run_start, index))
                run_start = None
        if run_start is not None and last - run_start >= minimum_quiet_windows:
            quiet_runs.append((run_start, last))
        energy_start: float | None
        energy_end: float | None
        if quiet_runs:
            quiet_start, quiet_end = max(quiet_runs, key=lambda run: run[1] - run[0])
            energy_start = quiet_start * samples_per_window / rate
            energy_end = min(asr_end, quiet_end * samples_per_window / rate)
            start, end = energy_start, energy_end
        else:
            energy_start = energy_end = None
            start, end = asr_start, asr_end
        if end > start:
            gaps.append(
                RefinedGap(
                    start=start,
                    end=end,
                    asr_start=asr_start,
                    asr_end=asr_end,
                    energy_start=energy_start,
                    energy_end=energy_end,
                    noise_floor_rms=noise_floor,
                    threshold_rms=threshold,
                )
            )
    return tuple(gaps)
