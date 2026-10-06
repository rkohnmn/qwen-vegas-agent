"""Build the allowlisted model-facing view of an internal catalog."""

from __future__ import annotations

from typing import Any

_CATALOG_GROUPS = ("transitions", "video_fx", "audio_fx", "text_presets", "sfx")


def catalog_summary(catalog: dict[str, Any]) -> dict[str, Any]:
    """Return catalog keys and safe selection metadata, never paths or plugin IDs."""
    entries: list[dict[str, Any]] = []
    for group in _CATALOG_GROUPS:
        for entry in catalog.get(group, []):
            summary_entry: dict[str, Any] = {
                "key": entry["key"],
                "kind": entry["kind"],
                "tags": list(entry["tags"]),
                "params_mode": entry["params_mode"],
            }
            if "default_duration_frames" in entry:
                summary_entry["default_duration_frames"] = entry["default_duration_frames"]
            if "supports_color_override" in entry:
                summary_entry["supports_color_override"] = entry["supports_color_override"]
            entries.append(summary_entry)
    return {"schema_version": catalog["schema_version"], "entries": entries}
