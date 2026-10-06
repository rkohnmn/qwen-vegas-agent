from __future__ import annotations

import math
import random
import wave
from array import array
from pathlib import Path

from orchestrator.verifier import verify_audio


def _write_speech_like_fixture(path: Path, *, sample_rate: int = 16000) -> int:
    """Generate deterministic band-limited speech-shaped bursts and room noise."""
    generator = random.Random(314159)
    samples = array("h")
    low_state = 0.0
    previous_low = 0.0
    band_state = 0.0
    burst_ranges = ((2400, 6800), (9600, 13600))
    attack = int(sample_rate * 0.012)
    release = int(sample_rate * 0.018)
    for index in range(sample_rate):
        white = generator.uniform(-1.0, 1.0)
        low_state += 0.16 * (white - low_state)
        high_passed = 0.96 * (band_state + low_state - previous_low)
        band_state = high_passed
        previous_low = low_state
        envelope = 0.0
        for start, end in burst_ranges:
            if start <= index < end:
                attack_gain = min(1.0, (index - start + 1) / attack)
                release_gain = min(1.0, (end - index) / release)
                envelope = min(attack_gain, release_gain)
                break
        amplitude = 4800.0 * envelope + 48.0
        samples.append(max(-32768, min(32767, round(band_state * amplitude))))
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(samples.tobytes())
    return sample_rate // 2


def test_speech_like_generated_fixture_runs_through_default_verifier(tmp_path: Path) -> None:
    audio_path = tmp_path / "generated-speech-like.wav"
    join = _write_speech_like_fixture(audio_path)

    report = verify_audio(audio_path, [join])

    assert report["passed"] is True
    by_name = {check["name"]: check for check in report["checks"]}
    assert by_name["click_discontinuity"]["measured"] <= 0.12
    assert by_name["level_step"]["measured"] <= 8.0
    assert math.isfinite(by_name["click_discontinuity"]["measured"])
