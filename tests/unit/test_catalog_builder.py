from __future__ import annotations

import json

import pytest

from orchestrator.catalog import (
    CatalogBuildError,
    build_catalog_from_dump,
    generate_tag_file,
    merge_tag_file,
    model_catalog_summary,
    normalize_catalog_name,
)
from orchestrator.contracts import validate


def plugin_dump() -> dict[str, object]:
    return {
        "plugins": [
            {
                "category": "transition",
                "name": "Soft Dissolve",
                "unique_id": "{fixture-a}",
                "is_ofx": False,
                "depth": 1,
            },
            {
                "category": "transition",
                "name": "Soft Dissolve",
                "unique_id": "{fixture-b}",
                "is_ofx": True,
                "depth": 2,
            },
            {
                "category": "video_fx",
                "name": "Color Curve",
                "unique_id": "{fixture-video}",
                "is_ofx": True,
            },
        ]
    }


def test_catalog_keys_are_stable_and_collision_safe_for_duplicate_names() -> None:
    first, warnings = build_catalog_from_dump(plugin_dump())
    reversed_dump = {"plugins": list(reversed(plugin_dump()["plugins"] or []))}
    second, _ = build_catalog_from_dump(reversed_dump)

    keys = [entry["key"] for entry in first["transitions"]]
    assert len(keys) == len(set(keys)) == 2
    assert sorted(keys) == sorted(entry["key"] for entry in second["transitions"])
    assert first["plugin_list_hash"] == second["plugin_list_hash"]
    assert warnings == []
    assert validate("catalog", first) == []


def test_generated_tag_file_disables_everything_except_explicit_transition_allowlist() -> None:
    catalog, _ = build_catalog_from_dump(plugin_dump())
    allowed_key = catalog["transitions"][0]["key"]
    tag_file = generate_tag_file(catalog, allowed_transitions={allowed_key})

    merged = merge_tag_file(catalog, tag_file)

    assert [entry["key"] for entry in merged["transitions"] if entry["enabled"]] == [allowed_key]
    assert all(not entry["enabled"] for entry in merged["video_fx"])
    assert validate("catalog", merged) == []


def test_tag_file_missing_entry_disables_catalog_entry() -> None:
    catalog, _ = build_catalog_from_dump(plugin_dump())
    tag_file = generate_tag_file(catalog)
    tag_file["entries"].pop()
    merged = merge_tag_file(catalog, tag_file)

    assert all(not entry["enabled"] for entry in merged["video_fx"])


def test_tag_file_rejects_unknown_keys_and_bad_duration() -> None:
    catalog, _ = build_catalog_from_dump(plugin_dump())
    tag_file = generate_tag_file(catalog)
    tag_file["entries"][0]["key"] = "tr.fake.abcdef12"
    with pytest.raises(CatalogBuildError):
        merge_tag_file(catalog, tag_file)

    tag_file = generate_tag_file(catalog)
    tag_file["entries"][0]["default_duration_frames"] = 0
    with pytest.raises(CatalogBuildError):
        merge_tag_file(catalog, tag_file)


def test_catalog_summary_omits_disabled_entries_and_private_fields() -> None:
    catalog, _ = build_catalog_from_dump(plugin_dump())
    tag_file = generate_tag_file(catalog)
    tag_file["entries"][0]["enabled"] = True
    tag_file["entries"][0]["tags"] = ["soft"]
    tag_file["entries"][0]["allowed_contexts"] = ["topic_boundary"]
    merged = merge_tag_file(catalog, tag_file)

    summary = model_catalog_summary(merged)
    encoded = json.dumps(summary)

    assert len(summary["entries"]) == 1
    assert "fixture-a" not in encoded
    assert "plugin_unique_id" not in encoded
    assert "path" not in encoded
    assert "Color Curve" not in encoded


def test_unclassified_generator_is_not_assumed_to_be_a_text_preset() -> None:
    catalog, warnings = build_catalog_from_dump(
        {"plugins": [{"category": "generator", "name": "Unknown Generator", "unique_id": "gen-1"}]}
    )

    assert warnings
    assert catalog["text_presets"] == []
    assert catalog["plugin_list_hash"].startswith("sha256:")


def test_dump_requires_stable_ids() -> None:
    with pytest.raises(CatalogBuildError):
        build_catalog_from_dump({"plugins": [{"category": "transition", "name": "No UID"}]})


def test_catalog_names_do_not_expose_absolute_path_components() -> None:
    assert normalize_catalog_name("Z:/profiles/private/item") == "item"
    assert normalize_catalog_name("/private/item") == "item"


def test_tag_file_cannot_enable_parameter_mode_without_proven_schema() -> None:
    catalog, _ = build_catalog_from_dump(plugin_dump())
    tag_file = generate_tag_file(catalog)
    tag_file["entries"][0]["params_mode"] = "params"

    with pytest.raises(CatalogBuildError, match="VQ-17"):
        merge_tag_file(catalog, tag_file)


def test_tag_file_rejects_path_like_tags_and_unknown_fields() -> None:
    catalog, _ = build_catalog_from_dump(plugin_dump())
    tag_file = generate_tag_file(catalog)
    tag_file["entries"][0]["tags"] = ["../../private"]
    with pytest.raises(CatalogBuildError):
        merge_tag_file(catalog, tag_file)

    tag_file = generate_tag_file(catalog)
    tag_file["unexpected"] = "ignored"
    with pytest.raises(CatalogBuildError):
        merge_tag_file(catalog, tag_file)
