"""Build the canonical words contract from ASR and measured audio gaps."""

from __future__ import annotations

from typing import Any

from .asr import AsrResult
from .gaps import GapThresholds, RefinedGap, refine_gaps


def build_words_document(
    result: AsrResult,
    audio_path: str,
    source_hash: str,
    fps: str,
    *,
    speaker_mode: str = "single",
    thresholds: GapThresholds | None = None,
    gap_sources: list[tuple[AsrResult, str]] | None = None,
) -> dict[str, Any]:
    """Preserve unaligned transcript tokens without inventing their timing."""
    if not result.words:
        raise ValueError("ASR returned no words")
    word_rows: list[dict[str, Any]] = []
    segment_map: dict[tuple[str, int], list[str]] = {}
    for index, word in enumerate(result.words):
        word_id = f"w{index + 1}"
        word_rows.append(
            {
                "id": word_id,
                "text": word.text,
                "start": word.start if word.aligned else None,
                "end": word.end if word.aligned else None,
                "alignment_status": "aligned" if word.aligned else "unaligned",
                "speaker": None,
                "speaker_conf": 0.0,
                "word_conf": word.confidence,
                "track": word.track,
            }
        )
        segment_map.setdefault((word.track, word.segment_index), []).append(word_id)
    segments = [
        {"id": f"s{index + 1}", "word_ids": ids, "speaker": None}
        for index, ids in enumerate(segment_map.values())
        if ids
    ]
    gap_rows: list[RefinedGap] = []
    for gap_result, gap_audio in gap_sources or [(result, audio_path)]:
        gap_rows.extend(refine_gaps(gap_result, gap_audio, thresholds))
    gap_rows.sort(key=lambda gap: gap.start)
    gaps = [gap.as_dict(f"g{index + 1}") for index, gap in enumerate(gap_rows)]
    return {
        "schema_version": "2.0.0",
        "source_hash": source_hash,
        "fps": fps,
        "asr": {
            "engine": result.engine,
            "model": result.model,
            "align_model": result.align_model,
            "params_hash": result.params_hash,
            "detected_language": result.detected_language,
            "language_confidence": result.language_confidence,
            "device": result.device,
            "compute_type": result.compute_type,
            "fallback_reason": result.fallback_reason,
        },
        "speaker_mode": speaker_mode,
        "words": word_rows,
        "segments": segments,
        "gaps": gaps,
        "audio_events": [],
    }
