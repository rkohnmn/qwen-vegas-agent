"""ASR interfaces, deterministic fixtures, and lazy WhisperX integration."""

from __future__ import annotations

import gc
import hashlib
import importlib
import json
import logging
import math
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

LOGGER = logging.getLogger(__name__)
_INFERENCE_LOCK = threading.Lock()
_WORD_SPLIT = re.compile(r"\S+")


class AsrError(RuntimeError):
    """Safe ASR stage failure without transcript or path details."""


@dataclass(frozen=True, slots=True)
class AsrWord:
    text: str
    start: float | None
    end: float | None
    confidence: float
    aligned: bool
    segment_index: int
    track: str = "audio_0"


@dataclass(frozen=True, slots=True)
class AsrResult:
    words: tuple[AsrWord, ...]
    detected_language: str | None
    language_confidence: float | None
    model: str
    align_model: str
    params_hash: str
    device: str
    compute_type: str
    fallback_reason: str | None = None
    engine: str = "whisperx"


class AsrEngine(Protocol):
    def transcribe_aligned(self, audio_path: str | Path) -> AsrResult:
        """Return word-level output; missing alignment is represented without times."""


@dataclass(frozen=True, slots=True)
class WhisperXConfig:
    model: str = "small"
    device: str = "auto"
    compute_type: str = "int8_float16"
    language: str = "auto"
    batch_size: int = 1
    cpu_threads: int = 8
    model_cache_dir: Path = Path("cache/asr_models")


def _params_hash(config: WhisperXConfig, device: str, compute_type: str) -> str:
    data = {
        "engine": "whisperx",
        "model": config.model,
        "device": device,
        "compute_type": compute_type,
        "language": config.language,
        "batch_size": config.batch_size,
        "cpu_threads": config.cpu_threads,
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _normal_word(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def _valid_time(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if not math.isfinite(float(value)) or value < 0:
        return None
    return float(value)


def _score(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    number = float(value)
    return number if math.isfinite(number) and 0 <= number <= 1 else 0.0


def _unaligned_words(text: str, segment_index: int) -> list[AsrWord]:
    return [
        AsrWord(token, None, None, 0.0, False, segment_index)
        for token in _WORD_SPLIT.findall(text.strip())
    ]


def _words_from_segments(
    raw_segments: Sequence[object],
    aligned_segments: Sequence[object] | None,
) -> tuple[AsrWord, ...]:
    aligned_by_segment = list(aligned_segments or [])
    output: list[AsrWord] = []
    for segment_index, raw_value in enumerate(raw_segments):
        raw = raw_value if isinstance(raw_value, Mapping) else {}
        text_value = raw.get("text", "")
        text = text_value if isinstance(text_value, str) else ""
        aligned_value = (
            aligned_by_segment[segment_index] if segment_index < len(aligned_by_segment) else None
        )
        aligned = aligned_value if isinstance(aligned_value, Mapping) else {}
        word_rows = aligned.get("words", [])
        if not isinstance(word_rows, list) or not word_rows:
            output.extend(_unaligned_words(text, segment_index))
            continue
        aligned_texts = [
            row.get("word", "").strip()
            for row in word_rows
            if isinstance(row, Mapping) and isinstance(row.get("word", ""), str)
        ]
        raw_tokens = _WORD_SPLIT.findall(text.strip())
        raw_normalized = [_normal_word(token) for token in raw_tokens]
        aligned_normalized = [_normal_word(token) for token in aligned_texts]
        if (
            raw_tokens
            and all(raw_normalized)
            and (
                len(raw_normalized) != len(aligned_normalized)
                or any(
                    left != right
                    for left, right in zip(raw_normalized, aligned_normalized, strict=False)
                )
            )
        ):
            output.extend(_unaligned_words(text, segment_index))
            continue
        for word_row in word_rows:
            if not isinstance(word_row, Mapping):
                continue
            word_text = word_row.get("word", "")
            if not isinstance(word_text, str) or not word_text.strip():
                continue
            start = _valid_time(word_row.get("start"))
            end = _valid_time(word_row.get("end"))
            is_aligned = start is not None and end is not None and end >= start
            output.append(
                AsrWord(
                    text=word_text.strip(),
                    start=start if is_aligned else None,
                    end=end if is_aligned else None,
                    confidence=_score(word_row.get("score")),
                    aligned=is_aligned,
                    segment_index=segment_index,
                )
            )
    return tuple(output)


class FakeAsrEngine:
    """Deterministic fixture-backed engine used by offline tests and evals."""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        self._fixture = dict(fixture)

    @classmethod
    def from_fixture(cls, path: str | Path) -> FakeAsrEngine:
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise AsrError("fake ASR fixture could not be read") from None
        if not isinstance(value, dict):
            raise AsrError("fake ASR fixture has an invalid shape")
        return cls(value)

    def transcribe_aligned(self, audio_path: str | Path) -> AsrResult:
        del audio_path
        rows = self._fixture.get("words", [])
        if not isinstance(rows, list):
            raise AsrError("fake ASR fixture has an invalid shape")
        words: list[AsrWord] = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                raise AsrError("fake ASR fixture has an invalid word row")
            start = _valid_time(row.get("start"))
            end = _valid_time(row.get("end"))
            aligned = bool(row.get("aligned", start is not None and end is not None))
            if aligned and (start is None or end is None or end < start):
                raise AsrError("fake ASR fixture has invalid aligned timing")
            segment_index = row.get("segment_index", 0)
            if not isinstance(segment_index, int) or isinstance(segment_index, bool):
                raise AsrError("fake ASR fixture has invalid segment mapping")
            words.append(
                AsrWord(
                    text=row["text"],
                    start=start if aligned else None,
                    end=end if aligned else None,
                    confidence=_score(row.get("confidence")),
                    aligned=aligned,
                    segment_index=segment_index,
                )
            )
        language = self._fixture.get("detected_language")
        language_confidence = self._fixture.get("language_confidence")
        return AsrResult(
            words=tuple(words),
            detected_language=language if isinstance(language, str) else None,
            language_confidence=_score(language_confidence)
            if language_confidence is not None
            else None,
            model=str(self._fixture.get("model", "fake")),
            align_model=str(self._fixture.get("align_model", "fake-align")),
            params_hash=str(self._fixture.get("params_hash", "fake-v1")),
            device="cpu",
            compute_type="fake",
            engine=str(self._fixture.get("engine", "fake")),
        )


class WhisperXEngine:
    """WhisperX adapter with serialized inference and automatic CPU fallback."""

    def __init__(self, config: WhisperXConfig | None = None) -> None:
        self.config = config or WhisperXConfig()

    def transcribe_aligned(self, audio_path: str | Path) -> AsrResult:
        path = Path(audio_path)
        if not path.is_file():
            raise AsrError("normalized audio file does not exist")
        with _INFERENCE_LOCK:
            torch, whisperx = self._imports()
            device, compute_type, fallback_reason = self._runtime(torch)
            try:
                return self._transcribe_on_device(
                    path, torch, whisperx, device, compute_type, fallback_reason
                )
            except Exception as error:
                if device != "cuda" or not self._is_cuda_oom(error):
                    raise AsrError("WhisperX transcription or alignment failed") from None
                reason = "CUDA ran out of memory; retrying serialized inference on CPU"
                LOGGER.warning("%s", reason)
                gc.collect()
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass
                return self._transcribe_on_device(path, torch, whisperx, "cpu", "int8", reason)

    def _imports(self) -> tuple[Any, Any]:
        try:
            torch = importlib.import_module("torch")
            whisperx = importlib.import_module("whisperx")
        except ImportError:
            raise AsrError(
                "WhisperX dependencies are not installed; install the optional ASR requirements"
            ) from None
        return torch, whisperx

    def _runtime(self, torch: Any) -> tuple[str, str, str | None]:
        requested = self.config.device
        cuda_available = bool(torch.cuda.is_available())
        if requested == "cpu":
            return "cpu", "int8", None
        if requested in ("auto", "cuda") and cuda_available:
            compute = self.config.compute_type
            if compute not in ("int8", "int8_float16", "float16", "float32"):
                compute = "int8_float16"
            return "cuda", compute, None
        reason = "CUDA unavailable in active Python; using CPU int8"
        LOGGER.warning("%s", reason)
        return "cpu", "int8", reason

    @staticmethod
    def _is_cuda_oom(error: Exception) -> bool:
        return type(error).__name__ == "OutOfMemoryError" or "out of memory" in str(error).lower()

    def _transcribe_on_device(
        self,
        path: Path,
        torch: Any,
        whisperx: Any,
        device: str,
        compute_type: str,
        fallback_reason: str | None,
    ) -> AsrResult:
        config = self.config
        model = whisperx.load_model(
            config.model,
            device,
            compute_type=compute_type,
            language=None if config.language == "auto" else config.language,
            download_root=str(config.model_cache_dir),
            threads=config.cpu_threads,
        )
        audio = whisperx.load_audio(str(path))
        detected_language: str | None = config.language if config.language != "auto" else None
        language_confidence: float | None = None
        if detected_language is None:
            detected_language, language_confidence = self._detect_language(model, audio, whisperx)
        raw = model.transcribe(
            audio,
            batch_size=config.batch_size,
            language=detected_language,
        )
        if detected_language is None:
            value = raw.get("language")
            detected_language = value if isinstance(value, str) else None
        raw_segments = raw.get("segments", [])
        if not isinstance(raw_segments, list):
            raw_segments = []

        del model
        gc.collect()
        if device == "cuda":
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass

        words: tuple[AsrWord, ...]
        align_name = "unavailable"
        try:
            if not detected_language:
                raise ValueError("language detection returned no language")
            align_model, metadata = whisperx.load_align_model(
                language_code=detected_language,
                device=device,
                model_dir=str(config.model_cache_dir),
            )
            aligned = whisperx.align(
                raw_segments,
                align_model,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )
            aligned_segments = aligned.get("segments", [])
            words = _words_from_segments(
                raw_segments,
                aligned_segments if isinstance(aligned_segments, list) else None,
            )
            align_name = str(
                metadata.get("model_name")
                or metadata.get("type")
                or f"whisperx-default:{detected_language}"
            )
            del align_model
            gc.collect()
            if device == "cuda":
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass
        except Exception as error:
            if device == "cuda" and self._is_cuda_oom(error):
                raise
            LOGGER.warning(
                "WhisperX forced alignment unavailable (%s); retaining words without times",
                type(error).__name__,
            )
            words = tuple(
                word
                for index, segment in enumerate(raw_segments)
                if isinstance(segment, Mapping)
                for word in _unaligned_words(
                    segment.get("text", "") if isinstance(segment.get("text"), str) else "",
                    index,
                )
            )
            align_name = "unavailable"

        return AsrResult(
            words=words,
            detected_language=detected_language,
            language_confidence=language_confidence,
            model=config.model,
            align_model=align_name,
            params_hash=_params_hash(config, device, compute_type),
            device=device,
            compute_type=compute_type,
            fallback_reason=fallback_reason,
        )

    def _detect_language(
        self, pipeline: Any, audio: Any, whisperx: Any
    ) -> tuple[str | None, float | None]:
        try:
            asr_module = importlib.import_module("whisperx.asr")
            sample_count = int(asr_module.N_SAMPLES)
            sample = audio[:sample_count]
            n_mels = pipeline.model.feat_kwargs.get("feature_size", 80)
            mel = asr_module.log_mel_spectrogram(
                sample,
                n_mels=n_mels,
                padding=max(0, sample_count - int(audio.shape[0])),
            )
            encoded = pipeline.model.encode(mel)
            candidates = pipeline.model.model.detect_language(encoded)
            token, probability = candidates[0][0]
            language = str(token)[2:-2]
            confidence = float(probability)
            if not language or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                return None, None
            return language, confidence
        except Exception as error:
            LOGGER.info(
                "WhisperX language confidence unavailable (%s)",
                type(error).__name__,
            )
            return None, None
