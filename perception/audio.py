"""Read-only source hashing and per-stream ffmpeg WAV extraction."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from orchestrator.childenv import safe_child_environment


class AudioExtractionError(RuntimeError):
    """Safe failure while producing normalized analysis audio."""


@dataclass(frozen=True, slots=True)
class AudioArtifact:
    path: Path
    source_hash: str
    cache_key: str
    stream_index: int
    sample_rate: int
    sample_count: int


def hash_media_file(path: str | Path) -> str:
    """Return a streaming SHA-256 without changing the media file."""
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise AudioExtractionError("source media could not be read") from None
    return "sha256:" + digest.hexdigest()


def _cache_key(source_hash: str, stream_index: int, duration_limit_s: int | None) -> str:
    parameters = {
        "source_hash": source_hash,
        "stream_index": stream_index,
        "sample_rate": 16000,
        "channels": 1,
        "codec": "pcm_s16le",
        "duration_limit_s": duration_limit_s,
    }
    encoded = json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _wave_sample_count(path: Path) -> int | None:
    try:
        with wave.open(str(path), "rb") as audio:
            if (
                audio.getnchannels() != 1
                or audio.getsampwidth() != 2
                or audio.getframerate() != 16000
            ):
                return None
            frames = audio.getnframes()
            return frames if frames > 0 else None
    except (OSError, wave.Error):
        return None


def read_pcm16_mono(path: str | Path) -> tuple[array[int], int]:
    """Read normalized mono PCM16 WAV samples for deterministic audio-boundary analysis."""
    try:
        with wave.open(str(path), "rb") as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
                raise AudioExtractionError("audio analysis requires mono PCM16 WAV")
            samples = array("h")
            samples.frombytes(audio.readframes(audio.getnframes()))
            if sys.byteorder != "little":
                samples.byteswap()
            return samples, audio.getframerate()
    except (OSError, wave.Error):
        raise AudioExtractionError("audio analysis WAV could not be read") from None


def extract_audio_stream(
    media_path: str | Path,
    stream_index: int,
    cache_dir: str | Path,
    *,
    ffmpeg_executable: str = "ffmpeg",
    timeout_s: int = 1800,
    duration_limit_s: int | None = None,
) -> AudioArtifact:
    """Extract one global ffprobe stream index to cached 16 kHz mono PCM WAV."""
    if stream_index < 0:
        raise ValueError("stream_index must be nonnegative")
    if timeout_s < 1 or timeout_s > 7200:
        raise ValueError("timeout_s must be between 1 and 7200")
    if duration_limit_s is not None and not 1 <= duration_limit_s <= 36000:
        raise ValueError("duration_limit_s must be between 1 and 36000")
    source = Path(media_path)
    if not source.is_file():
        raise AudioExtractionError("selected media file does not exist")
    source_hash = hash_media_file(source)
    key = _cache_key(source_hash, stream_index, duration_limit_s)
    cache_root = Path(cache_dir)
    target = cache_root / "audio" / key[:2] / f"{key}.wav"
    target.parent.mkdir(parents=True, exist_ok=True)
    cached_count = _wave_sample_count(target)
    if cached_count is not None:
        return AudioArtifact(
            target, source_hash, "sha256:" + key, stream_index, 16000, cached_count
        )
    if target.exists():
        try:
            target.unlink()
        except OSError:
            raise AudioExtractionError("invalid cached audio could not be replaced") from None

    executable = shutil.which(ffmpeg_executable)
    if executable is None:
        raise AudioExtractionError("ffmpeg is not installed or not available on PATH")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=key[:12] + "-", suffix=".wav", dir=target.parent, delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
        command = [
            executable,
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
        ]
        if duration_limit_s is not None:
            command.extend(["-t", str(duration_limit_s)])
        command.extend(
            [
                "-map",
                f"0:{stream_index}",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                "-f",
                "wav",
                str(temp_path),
            ]
        )
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                shell=False,
                env=safe_child_environment(),
            )
        except FileNotFoundError:
            raise AudioExtractionError("ffmpeg is not installed or not available on PATH") from None
        except subprocess.TimeoutExpired:
            raise AudioExtractionError("audio extraction timed out") from None
        except OSError:
            raise AudioExtractionError("ffmpeg could not be started") from None
        if completed.returncode:
            raise AudioExtractionError("ffmpeg could not extract the selected audio stream")
        sample_count = _wave_sample_count(temp_path)
        if sample_count is None:
            raise AudioExtractionError("ffmpeg output was not a valid 16 kHz mono PCM WAV")
        os.replace(temp_path, target)
        temp_path = None
        return AudioArtifact(
            target, source_hash, "sha256:" + key, stream_index, 16000, sample_count
        )
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def mix_normalized_audio(
    audio_paths: list[str | Path],
    output_wav: str | Path,
    *,
    ffmpeg_executable: str = "ffmpeg",
    timeout_s: int = 600,
) -> Path:
    """Create a reference-only mixdown from normalized stream WAVs."""
    if not audio_paths:
        raise AudioExtractionError("no normalized audio streams are available")
    output = Path(output_wav)
    for audio_path in audio_paths:
        if _wave_sample_count(Path(audio_path)) is None:
            raise AudioExtractionError("normalized audio stream is invalid")
    if len(audio_paths) == 1:
        try:
            shutil.copyfile(audio_paths[0], output)
        except OSError:
            raise AudioExtractionError("reference audio could not be prepared") from None
        return output
    executable = shutil.which(ffmpeg_executable)
    if executable is None:
        raise AudioExtractionError("ffmpeg is not installed or not available on PATH")
    command = [executable, "-nostdin", "-v", "error", "-y"]
    for audio_path in audio_paths:
        command.extend(["-i", str(audio_path)])
    inputs = "".join(f"[{index}:a]" for index in range(len(audio_paths)))
    command.extend(
        [
            "-filter_complex",
            f"{inputs}amix=inputs={len(audio_paths)}:duration=longest:normalize=1,"
            "aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono[mix]",
            "-map",
            "[mix]",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    )
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            shell=False,
            env=safe_child_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        raise AudioExtractionError("reference audio mixdown failed") from None
    if completed.returncode or _wave_sample_count(output) is None:
        raise AudioExtractionError("reference audio mixdown failed")
    return output
