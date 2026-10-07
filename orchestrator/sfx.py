"""Local-only SFX indexing and safe keyword lookup."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from orchestrator.catalog import catalog_key, normalize_catalog_name

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif"}
SUPPORTED_SAMPLE_RATES = {32000, 44100, 48000, 88200, 96000}
_SUPPORTED_CODECS = {
    ".wav": {"pcm_u8", "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm_f64le"},
    ".mp3": {"mp3"},
    ".flac": {"flac"},
    ".ogg": {"vorbis", "opus"},
    ".m4a": {"aac", "alac"},
    ".aac": {"aac"},
    ".aiff": {"pcm_s16be", "pcm_s24be", "pcm_s32be", "pcm_f32be"},
    ".aif": {"pcm_s16be", "pcm_s24be", "pcm_s32be", "pcm_f32be"},
}
_SAFE_TAG = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")


class SfxIndexError(ValueError):
    """Raised when a local SFX library cannot be indexed safely."""


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SfxIndexError("local audio measurement tool failed") from error


def _ffprobe_measure(path: Path) -> dict[str, Any]:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate,codec_name",
            "-show_entries",
            "format=duration,format_name",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode != 0:
        raise SfxIndexError("ffprobe could not inspect an audio file")
    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        duration = float(payload["format"]["duration"])
        sample_rate = int(stream["sample_rate"])
        codec_name = str(stream["codec_name"])
        format_name = str(payload["format"]["format_name"]).casefold()
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SfxIndexError("ffprobe returned invalid audio metadata") from error
    if not math.isfinite(duration) or duration <= 0:
        raise SfxIndexError("audio duration must be finite and positive")
    if sample_rate not in SUPPORTED_SAMPLE_RATES:
        raise SfxIndexError("audio sample rate is not supported")
    expected_codecs = _SUPPORTED_CODECS.get(path.suffix.lower(), set())
    if codec_name not in expected_codecs or not format_name:
        raise SfxIndexError("audio container or codec is not supported")
    measured = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ]
    )
    if measured.returncode != 0:
        raise SfxIndexError("ffmpeg loudness measurement failed")
    integrated = re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?)\s+LUFS", measured.stderr)
    peaks = re.findall(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", measured.stderr)
    if not integrated or not peaks:
        raise SfxIndexError("ffmpeg did not report integrated loudness and peak")
    return {
        "duration": duration,
        "sample_rate": sample_rate,
        "loudness_lufs": float(integrated[-1]),
        "peak_dbfs": float(peaks[-1]),
    }


def _license_is_valid(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in {
        "",
        "unlicensed",
        "unknown",
        "none",
        "unspecified",
    }


def _read_sidecar(path: Path) -> tuple[str, str, list[str]]:
    sidecar = path.with_suffix(".json")
    if not sidecar.exists():
        return "UNLICENSED", "local", []
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SfxIndexError("an SFX sidecar is not valid JSON") from error
    if not isinstance(data, Mapping) or set(data) - {"license", "source", "tags"}:
        raise SfxIndexError("an SFX sidecar contains unsupported fields")
    license_value = data.get("license", "UNLICENSED")
    source = data.get("source", "local")
    tags = data.get("tags", [])
    if not isinstance(source, str) or not source.strip() or len(source) > 160:
        raise SfxIndexError("SFX source metadata is invalid")
    if not isinstance(tags, list) or any(
        not isinstance(tag, str) or _SAFE_TAG.fullmatch(tag) is None for tag in tags
    ):
        raise SfxIndexError("SFX tags must be lowercase safe tokens")
    if len(tags) > 32 or len(set(tags)) != len(tags):
        raise SfxIndexError("SFX tags must be unique and contain at most 32 entries")
    if not isinstance(license_value, str) or not license_value.strip() or len(license_value) > 160:
        license_value = "UNLICENSED"
    return license_value.strip(), source.strip(), tags


def index_sfx_directory(
    directory: Path,
    *,
    measure: Callable[[Path], Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build an index without modifying or copying any source audio."""
    root = directory.resolve(strict=True)
    if not root.is_dir():
        raise SfxIndexError("SFX library path must be a directory")
    measure_file = measure or _ffprobe_measure
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    candidates = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )
    for path in candidates:
        if path.suffix.lower() == ".json":
            continue
        if path.is_symlink():
            warnings.append("symbolic link was skipped")
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            warnings.append("unsupported file extension was skipped")
            continue
        resolved_path = path.resolve(strict=True)
        if not resolved_path.is_relative_to(root):
            warnings.append("file resolving outside the library was skipped")
            continue
        relative = path.relative_to(root).as_posix()
        try:
            license_value, source, tags = _read_sidecar(path)
            metadata = dict(measure_file(path))
            duration = float(metadata["duration"])
            loudness = float(metadata["loudness_lufs"])
            peak = float(metadata["peak_dbfs"])
            sample_rate = metadata["sample_rate"]
        except SfxIndexError:
            raise
        except (KeyError, TypeError, ValueError, OSError) as error:
            raise SfxIndexError("audio metadata was incomplete or invalid") from error
        if (
            type(sample_rate) is not int
            or sample_rate not in SUPPORTED_SAMPLE_RATES
            or not all(math.isfinite(value) for value in (duration, loudness, peak))
            or duration <= 0
            or not -120 <= loudness <= 24
            or not -120 <= peak <= 24
        ):
            raise SfxIndexError("audio metadata is outside supported limits")
        with path.open("rb") as audio_file:
            fingerprint = hashlib.file_digest(audio_file, "sha256").hexdigest()
        identity = f"{relative.casefold()}:{fingerprint}"
        display_name = path.stem
        entry = {
            "key": catalog_key("sfx", display_name, identity),
            "name": display_name[:120],
            "kind": "sfx",
            "tags": tags or [normalize_catalog_name(path.stem)],
            "params_mode": "defaults_only",
            "enabled": _license_is_valid(license_value),
            "path": str(resolved_path),
            "relative_path": relative,
            "duration": duration,
            "sample_rate": sample_rate,
            "loudness_lufs": loudness,
            "peak_dbfs": peak,
            "fingerprint": fingerprint,
            "license": license_value,
            "source": source,
        }
        if not entry["enabled"]:
            warnings.append("SFX entry without license metadata is disabled")
        entries.append(entry)
    return {"schema_version": "1.0.0", "entries": entries}, warnings


def search_sfx(
    index: Mapping[str, Any], query: str = "", tags: set[str] | None = None
) -> list[str]:
    """Return enabled keys matching safe keyword and tag terms."""
    terms = {part for part in re.findall(r"[a-z0-9]+", query.casefold()) if part}
    required_tags = tags or set()
    matches: list[str] = []
    for entry in index.get("entries", []):
        if not isinstance(entry, Mapping) or entry.get("enabled") is not True:
            continue
        entry_tags = set(entry.get("tags", []))
        searchable = {str(entry.get("name", "")).casefold(), *entry_tags}
        searchable.update(re.findall(r"[a-z0-9]+", " ".join(searchable)))
        if required_tags <= entry_tags and (not terms or terms & searchable):
            key = entry.get("key")
            if isinstance(key, str):
                matches.append(key)
    return sorted(matches)
