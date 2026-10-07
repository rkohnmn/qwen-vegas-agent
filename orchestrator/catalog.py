"""Deterministic construction and policy checks for the closed catalog."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from orchestrator.contracts import catalog_summary, check_catalog, validate

CATALOG_VERSION = "1.1.0"
TAG_FILE_VERSION = "1.0.0"
_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("transition", "transitions", "tr"),
    ("video_fx", "video_fx", "vfx"),
    ("audio_fx", "audio_fx", "afx"),
    ("text_preset", "text_presets", "txt"),
    ("sfx", "sfx", "sfx"),
)


class CatalogBuildError(ValueError):
    """Raised when a dump or tag file cannot produce a safe catalog."""


def normalize_catalog_name(name: str) -> str:
    """Normalize a display name for a stable, model-safe catalog key."""
    if (len(name) > 2 and name[1] == ":" and name[2] in (chr(92), "/")) or name.startswith(
        ("\\", "/")
    ):
        return "item"
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    collapsed = re.sub(r"[^a-z0-9]+", "-", normalized.lower())
    return (re.sub(r"-+", "-", collapsed).strip("-") or "item")[:48]


def catalog_key(category_prefix: str, name: str, stable_id: str) -> str:
    """Build a deterministic key with a short identity hash for duplicate names."""
    if not stable_id.strip():
        raise CatalogBuildError("catalog entries require a stable identity")
    suffix = hashlib.sha256(stable_id.encode("utf-8")).hexdigest()[:8]
    return f"{category_prefix}.{normalize_catalog_name(name)}.{suffix}"


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _plugin_list_hash(plugins: Sequence[Mapping[str, Any]]) -> str:
    normalized = [
        {
            "category": item.get("category"),
            "name": item.get("name"),
            "unique_id": item.get("unique_id"),
            "is_ofx": item.get("is_ofx", False),
            "depth": item.get("depth", 0),
        }
        for item in plugins
    ]
    normalized.sort(
        key=lambda item: (
            str(item["category"]),
            str(item["unique_id"]),
            str(item["name"]),
            int(item["depth"]),
        )
    )
    return _canonical_hash(normalized)


def build_catalog_from_dump(
    plugin_dump: Mapping[str, Any], *, vegas_version: str = "unknown"
) -> tuple[dict[str, Any], list[str]]:
    """Build an internal catalog from CatalogDump JSON and return safe warnings.

    Generator entries are not assumed to be text presets. The dump format must
    explicitly classify a text preset before it can enter the closed catalog.
    """
    raw_plugins = plugin_dump.get("plugins")
    if not isinstance(raw_plugins, list):
        raise CatalogBuildError("plugin dump must contain a plugins array")
    plugins: list[Mapping[str, Any]] = []
    for item in raw_plugins:
        if not isinstance(item, Mapping):
            raise CatalogBuildError("plugin dump contains an invalid entry")
        if not isinstance(item.get("category"), str) or not isinstance(item.get("name"), str):
            raise CatalogBuildError("plugin dump entry is missing its category or name")
        if not isinstance(item.get("unique_id"), str) or not item["unique_id"].strip():
            raise CatalogBuildError("plugin dump entry is missing its stable identity")
        depth = item.get("depth", 0)
        if type(depth) is not int or depth < 0:
            raise CatalogBuildError("plugin dump depth is invalid")
        is_ofx = item.get("is_ofx", False)
        if type(is_ofx) is not bool:
            raise CatalogBuildError("plugin dump OFX flag is invalid")
        plugins.append(item)

    catalog: dict[str, Any] = {
        "schema_version": CATALOG_VERSION,
        "vegas_version": vegas_version,
        "plugin_list_hash": _plugin_list_hash(plugins),
        "transitions": [],
        "video_fx": [],
        "audio_fx": [],
        "text_presets": [],
        "sfx": [],
    }
    category_map = {
        source: (group, prefix)
        for source, group, prefix in (
            ("transition", "transitions", "tr"),
            ("video_fx", "video_fx", "vfx"),
            ("audio_fx", "audio_fx", "afx"),
            ("text_preset", "text_presets", "txt"),
        )
    }
    warnings: list[str] = []
    for item in plugins:
        category = str(item["category"])
        mapped = category_map.get(category)
        if mapped is None:
            warnings.append("unclassified plugin category was omitted from the catalog")
            continue
        group, prefix = mapped
        key = catalog_key(prefix, str(item["name"]), str(item["unique_id"]))
        entry: dict[str, Any] = {
            "key": key,
            "kind": category,
            "tags": [],
            "params_mode": "defaults_only",
            "enabled": False,
            "plugin_unique_id": str(item["unique_id"]),
            "is_ofx": bool(item.get("is_ofx", False)),
        }
        if category == "transition":
            # Disabled suggestion only; Vegas duration is never inferred.
            entry["default_duration_frames"] = 12
        elif category == "text_preset":
            entry["params_mode"] = "preset_only"
            entry["presets"] = []
            entry["supports_color_override"] = "unknown"
        catalog[group].append(entry)

    issues = validate("catalog", catalog)
    issues.extend(check_catalog(catalog))
    if issues:
        raise CatalogBuildError("generated catalog failed contract validation")
    return catalog, warnings


def generate_tag_file(
    catalog: Mapping[str, Any], *, allowed_transitions: set[str] | None = None
) -> dict[str, Any]:
    """Create a human-editable JSON tag file with a closed, disabled default."""
    allowlist = allowed_transitions or set()
    catalog_keys: set[str] = set()
    entries: list[dict[str, Any]] = []
    for _source, group, _prefix in _GROUPS:
        for entry in catalog.get(group, []):
            if not isinstance(entry, Mapping) or not isinstance(entry.get("key"), str):
                raise CatalogBuildError("catalog contains an invalid entry")
            key = str(entry["key"])
            catalog_keys.add(key)
            kind = str(entry.get("kind", ""))
            tag_entry: dict[str, Any] = {
                "key": key,
                "tags": [],
                "params_mode": "preset_only" if kind == "text_preset" else "defaults_only",
                "allowed_contexts": [],
                "enabled": kind == "transition" and key in allowlist,
            }
            if kind == "transition":
                tag_entry["default_duration_frames"] = 12
            entries.append(tag_entry)
    if allowlist - catalog_keys:
        raise CatalogBuildError("transition allowlist contains an unknown catalog key")
    return {"schema_version": TAG_FILE_VERSION, "entries": entries}


def merge_tag_file(catalog: Mapping[str, Any], tag_file: Mapping[str, Any]) -> dict[str, Any]:
    """Apply human tag overrides while rejecting unknown keys and unsafe values."""
    if set(tag_file) - {"schema_version", "entries"}:
        raise CatalogBuildError("tag file contains unknown fields")
    if tag_file.get("schema_version") != TAG_FILE_VERSION:
        raise CatalogBuildError("tag file version is unsupported")
    overrides = tag_file.get("entries")
    if not isinstance(overrides, list):
        raise CatalogBuildError("tag file must contain an entries array")
    by_key: dict[str, Mapping[str, Any]] = {}
    for override in overrides:
        if not isinstance(override, Mapping) or not isinstance(override.get("key"), str):
            raise CatalogBuildError("tag file contains an invalid entry")
        if set(override) - {
            "key",
            "tags",
            "allowed_contexts",
            "params_mode",
            "enabled",
            "default_duration_frames",
        }:
            raise CatalogBuildError("tag file entry contains unknown fields")
        key = str(override["key"])
        if key in by_key:
            raise CatalogBuildError("tag file contains a duplicate key")
        by_key[key] = override

    result: dict[str, Any] = deepcopy(dict(catalog))
    known_keys: set[str] = set()
    for _source, group, _prefix in _GROUPS:
        for entry in result.get(group, []):
            key = entry["key"]
            known_keys.add(key)
            override = by_key.get(key)
            if override is None:
                entry["enabled"] = False
                continue
            tags = override.get("tags", [])
            contexts = override.get("allowed_contexts", [])
            if (
                not isinstance(tags, list)
                or any(not isinstance(tag, str) or not tag.strip() for tag in tags)
                or len(set(tags)) != len(tags)
                or any(re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", tag) is None for tag in tags)
            ):
                raise CatalogBuildError("tag file tags must be unique non-empty strings")
            if not isinstance(contexts, list) or any(
                not isinstance(context, str) or not context.strip() for context in contexts
            ):
                raise CatalogBuildError("tag file contexts must be non-empty strings")
            if type(override.get("enabled")) is not bool:
                raise CatalogBuildError("tag file enabled must be a boolean")
            if entry["kind"] == "transition":
                duration = override.get("default_duration_frames")
                if type(duration) is not int or duration < 1:
                    raise CatalogBuildError("enabled transition requires positive default frames")
                entry["default_duration_frames"] = duration
            params_mode = override.get("params_mode", entry["params_mode"])
            if params_mode not in {"params", "preset_only", "defaults_only"}:
                raise CatalogBuildError("tag file params_mode is invalid")
            if params_mode == "params":
                raise CatalogBuildError("parameter mode requires a VQ-17-backed parameter schema")
            entry.update(
                {
                    "tags": tags,
                    "allowed_contexts": contexts,
                    "enabled": override["enabled"],
                    "params_mode": params_mode,
                }
            )
            license_value = entry.get("license")
            if entry["kind"] == "sfx" and (
                not isinstance(license_value, str)
                or license_value.strip().casefold() in {"", "unlicensed", "unknown", "none"}
            ):
                entry["enabled"] = False
    if set(by_key) - known_keys:
        raise CatalogBuildError("tag file contains an unknown catalog key")
    issues = validate("catalog", result)
    issues.extend(check_catalog(result))
    if issues:
        raise CatalogBuildError("tagged catalog failed contract validation")
    return result


def model_catalog_summary(catalog: dict[str, Any]) -> dict[str, Any]:
    """Expose enabled entries only, using the contracts' strict field allowlist."""
    filtered = dict(catalog)
    for _source, group, _prefix in _GROUPS:
        filtered[group] = [
            entry
            for entry in catalog.get(group, [])
            if isinstance(entry, Mapping) and entry.get("enabled", True) is True
        ]
    return catalog_summary(filtered)
