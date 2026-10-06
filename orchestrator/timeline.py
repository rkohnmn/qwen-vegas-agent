"""Synthesize a contract timeline from read-only ffprobe metadata."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from perception.preflight import MediaProbe


def _nearest(value: Fraction) -> int:
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def build_timeline(
    probe: MediaProbe,
    source_hash: str,
    *,
    max_seconds: int | None = None,
) -> dict[str, Any]:
    """Build one linked source A/V group with integer lengths and rational fps."""
    if not probe.video_streams or probe.frame_rate is None or probe.duration is None:
        raise ValueError("preflight lacks a usable video stream, frame rate, or duration")
    fps = probe.frame_rate
    duration = probe.duration
    if max_seconds is not None:
        if max_seconds < 1:
            raise ValueError("max_seconds must be positive")
        duration = min(duration, Fraction(max_seconds, 1))
    duration_frames = max(1, _nearest(duration * fps))
    audio = probe.audio_streams
    tracks = [{"id": "v0", "kind": "video", "index": 0}]
    events = [
        {
            "id": "e0",
            "track_id": "v0",
            "group_id": "lg0",
            "start_frame": 0,
            "source_offset_frames": 0,
            "length_frames": duration_frames,
        }
    ]
    event_ids = ["e0"]
    for track_index, _stream in enumerate(audio):
        track_id = f"a{track_index}"
        event_id = f"e{track_index + 1}"
        tracks.append({"id": track_id, "kind": "audio", "index": track_index})
        events.append(
            {
                "id": event_id,
                "track_id": track_id,
                "group_id": "lg0",
                "start_frame": 0,
                "source_offset_frames": 0,
                "length_frames": duration_frames,
            }
        )
        event_ids.append(event_id)
    if not audio:
        raise ValueError("preflight contains no audio stream")
    return {
        "schema_version": "1.0.0",
        "source_hash": source_hash,
        "fps": f"{fps.numerator}/{fps.denominator}",
        "duration_frames": duration_frames,
        "tracks": tracks,
        "groups": [{"id": "lg0", "event_ids": event_ids}],
        "events": events,
    }
