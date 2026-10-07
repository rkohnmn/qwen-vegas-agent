from __future__ import annotations

from pathlib import Path

from orchestrator.capabilities import empty_capabilities, supported_operations
from orchestrator.catalog_compiler import CatalogPlacementConfig, compile_catalog_items


def _words() -> dict[str, object]:
    return {
        "words": [
            {"id": "w0", "start": 0.0, "end": 1.0, "speaker_key": "speaker_a"},
            {"id": "w1", "start": 1.05, "end": 1.15, "speaker_key": "speaker_a"},
            {"id": "w2", "start": 1.2, "end": 2.2, "speaker_key": "speaker_a"},
        ]
    }


def _timeline() -> dict[str, object]:
    return {
        "fps": "30/1",
        "duration_frames": 300,
        "tracks": [{"id": "a0", "kind": "audio", "index": 0}],
        "events": [{"id": "e0"}],
    }


def _capabilities(*operations: str, questions: list[str]) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "executor_id": "test-only-fake",
        "supported_operations": list(operations),
        "verified_questions": questions,
    }


def test_capability_claim_without_required_vq_evidence_is_not_enabled() -> None:
    capabilities = _capabilities("add_transition", questions=["VQ-05"])

    enabled, warnings = supported_operations(capabilities)

    assert enabled == set()
    assert warnings == ["operation capability is missing required VQ evidence"]


def test_transition_missing_or_disabled_key_is_rejected() -> None:
    edl = {
        "cuts": [{"id": "c0", "remove": {"from_word": "w1", "to_word": "w1"}}],
        "transitions": [
            {"at_cut": "c0", "offset_hint": "at", "type": "tr.missing.abcdef12", "reason": "test"}
        ],
    }
    catalog = {
        "transitions": [
            {
                "key": "tr.disabled.abcdef12",
                "kind": "transition",
                "enabled": False,
                "tags": [],
                "allowed_contexts": ["topic_boundary"],
                "default_duration_frames": 12,
            }
        ]
    }
    result = compile_catalog_items(
        edl, _words(), _timeline(), catalog, empty_capabilities(), working_root=Path.cwd()
    )

    assert [item["code"] for item in result.rejected_items] == [
        "E_CATALOG_MISSING",
    ]


def test_continuous_speech_transition_requires_dialogue_safe_tag() -> None:
    edl = {
        "cuts": [{"id": "c0", "remove": {"from_word": "w1", "to_word": "w1"}}],
        "transitions": [
            {"at_cut": "c0", "offset_hint": "at", "type": "tr.fade.abcdef12", "reason": "test"}
        ],
    }
    catalog = {
        "transitions": [
            {
                "key": "tr.fade.abcdef12",
                "kind": "transition",
                "enabled": True,
                "tags": [],
                "allowed_contexts": ["continuous_speech"],
                "default_duration_frames": 12,
            }
        ]
    }
    result = compile_catalog_items(
        edl,
        _words(),
        _timeline(),
        catalog,
        _capabilities("add_transition", questions=["VQ-05", "VQ-06"]),
        working_root=Path.cwd(),
    )

    assert result.operations == []
    assert result.rejected_items[0]["code"] == "E_TRANSITION_NOT_DIALOGUE_SAFE"


def test_transition_outside_catalog_allowed_context_is_rejected() -> None:
    edl = {
        "cuts": [{"id": "c0", "remove": {"from_word": "w1", "to_word": "w1"}}],
        "transitions": [
            {"at_cut": "c0", "offset_hint": "at", "type": "tr.fade.abcdef12", "reason": "test"}
        ],
    }
    catalog = {
        "transitions": [
            {
                "key": "tr.fade.abcdef12",
                "kind": "transition",
                "enabled": True,
                "tags": ["dialogue_safe"],
                "allowed_contexts": ["topic_boundary"],
                "default_duration_frames": 2,
            }
        ]
    }

    result = compile_catalog_items(
        edl,
        _words(),
        _timeline(),
        catalog,
        _capabilities("add_transition", questions=["VQ-05", "VQ-06"]),
        working_root=Path.cwd(),
    )

    assert result.operations == []
    assert result.rejected_items[0]["code"] == "E_TRANSITION_CONTEXT"


def test_transition_cannot_emit_without_executor_capability() -> None:
    edl = {
        "cuts": [{"id": "c0", "remove": {"from_word": "w1", "to_word": "w1"}}],
        "transitions": [
            {"at_cut": "c0", "offset_hint": "at", "type": "tr.fade.abcdef12", "reason": "test"}
        ],
    }
    catalog = {
        "transitions": [
            {
                "key": "tr.fade.abcdef12",
                "kind": "transition",
                "enabled": True,
                "tags": ["dialogue_safe"],
                "allowed_contexts": ["continuous_speech"],
                "default_duration_frames": 2,
            }
        ]
    }
    result = compile_catalog_items(
        edl, _words(), _timeline(), catalog, empty_capabilities(), working_root=Path.cwd()
    )

    assert result.operations == []
    assert result.rejected_items[0]["code"] == "E_UNSUPPORTED_OP"


def test_verified_transition_fails_closed_when_event_pair_is_unresolved() -> None:
    edl = {
        "cuts": [{"id": "c0", "remove": {"from_word": "w1", "to_word": "w1"}}],
        "transitions": [
            {"at_cut": "c0", "offset_hint": "at", "type": "tr.fade.abcdef12", "reason": "test"}
        ],
    }
    catalog = {
        "transitions": [
            {
                "key": "tr.fade.abcdef12",
                "kind": "transition",
                "enabled": True,
                "tags": ["dialogue_safe"],
                "allowed_contexts": ["continuous_speech"],
                "default_duration_frames": 2,
            }
        ]
    }

    result = compile_catalog_items(
        edl,
        _words(),
        _timeline(),
        catalog,
        _capabilities("add_transition", questions=["VQ-05", "VQ-06"]),
        working_root=Path.cwd(),
    )

    assert result.operations == []
    assert result.rejected_items[0]["code"] == "E_TRANSITION_BOUNDARY_UNRESOLVED"


def test_sfx_shifts_off_speech_peak_and_obeys_gain_and_capability(tmp_path: Path) -> None:
    asset = tmp_path / "effects" / "whoosh.wav"
    asset.parent.mkdir()
    asset.write_bytes(b"synthetic fixture")
    words = {"words": [{"id": "w0", "start": 1.0, "end": 1.2, "speaker_key": "speaker_a"}]}
    edl = {
        "sfx": [
            {
                "at_word": "w0",
                "offset_hint": "at",
                "key": "sfx.whoosh.abcdef12",
                "reason": "fixture",
            }
        ]
    }
    catalog = {
        "sfx": [
            {
                "key": "sfx.whoosh.abcdef12",
                "kind": "sfx",
                "enabled": True,
                "tags": ["whoosh"],
                "params_mode": "defaults_only",
                "path": str(asset),
                "duration": 0.1,
                "loudness_lufs": -40.0,
                "peak_dbfs": -2.0,
                "license": "CC0-1.0",
                "source": "synthetic fixture",
            }
        ]
    }
    samples = [0] * (3 * 48000)
    samples[48000] = 32767

    result = compile_catalog_items(
        edl,
        words,
        _timeline(),
        catalog,
        _capabilities("add_audio_event", questions=["VQ-18"]),
        working_root=tmp_path,
        audio_samples=samples,
        sample_rate=48000,
    )

    operation = result.operations[0]
    outcome = result.item_outcomes[0]
    assert operation["start_frame"] == 29
    assert operation["gain_db"] <= 0
    assert operation["gain_db"] + catalog["sfx"][0]["peak_dbfs"] <= -1
    assert outcome["status"] == "adjusted"
    assert outcome["delta_frames"] == 1
    assert outcome["adjustment_db"] < 0
    assert outcome["start_frame"] == 29
    assert outcome["duration_frames"] == 3
    assert outcome["catalog_key"] == "sfx.whoosh.abcdef12"


def test_sfx_gain_never_exceeds_policy_ceilings_for_measured_matrix(tmp_path: Path) -> None:
    asset = tmp_path / "whoosh.wav"
    asset.write_bytes(b"synthetic fixture")
    edl = {
        "sfx": [
            {
                "at_word": "w0",
                "offset_hint": "at",
                "key": "sfx.whoosh.abcdef12",
                "reason": "fixture",
            }
        ]
    }
    config = CatalogPlacementConfig(maximum_sfx_gain_db=-2.0, maximum_sfx_peak_dbfs=-1.0)
    measurements = [(-80.0, -60.0), (-40.0, -2.0), (-10.0, -0.25), (0.0, -3.0)]

    for loudness, peak in measurements:
        catalog = {
            "sfx": [
                {
                    "key": "sfx.whoosh.abcdef12",
                    "kind": "sfx",
                    "enabled": True,
                    "tags": ["whoosh"],
                    "path": str(asset),
                    "duration": 0.1,
                    "loudness_lufs": loudness,
                    "peak_dbfs": peak,
                    "license": "CC0-1.0",
                    "source": "synthetic fixture",
                }
            ]
        }
        result = compile_catalog_items(
            edl,
            {"words": [{"id": "w0", "start": 1.0, "end": 1.2}]},
            _timeline(),
            catalog,
            _capabilities("add_audio_event", questions=["VQ-18"]),
            working_root=tmp_path,
            audio_samples=[0] * (3 * 48000),
            sample_rate=48000,
            config=config,
        )

        operation = result.operations[0]
        gain = float(operation["gain_db"])
        assert gain <= config.maximum_sfx_gain_db
        assert gain + peak <= config.maximum_sfx_peak_dbfs


def test_sfx_is_rejected_when_capability_is_not_advertised(tmp_path: Path) -> None:
    asset = tmp_path / "whoosh.wav"
    asset.write_bytes(b"synthetic fixture")
    edl = {
        "sfx": [
            {
                "at_word": "w0",
                "offset_hint": "at",
                "key": "sfx.whoosh.abcdef12",
                "reason": "fixture",
            }
        ]
    }
    catalog = {
        "sfx": [
            {
                "key": "sfx.whoosh.abcdef12",
                "kind": "sfx",
                "enabled": True,
                "tags": [],
                "path": str(asset),
                "duration": 0.1,
                "loudness_lufs": -20.0,
                "peak_dbfs": -3.0,
                "license": "CC0-1.0",
                "source": "fixture",
            }
        ]
    }
    result = compile_catalog_items(
        edl,
        {"words": [{"id": "w0", "start": 1.0, "end": 1.2}]},
        _timeline(),
        catalog,
        empty_capabilities(),
        working_root=tmp_path,
        audio_samples=[0] * (3 * 48000),
        sample_rate=48000,
    )

    assert result.operations == []
    assert result.rejected_items[0]["code"] == "E_UNSUPPORTED_OP"


def test_effect_only_emits_default_parameters_when_capability_is_verified() -> None:
    edl = {"effects": [{"at_event": "e0", "key": "vfx.blur.abcdef12", "reason": "test"}]}
    catalog = {
        "video_fx": [
            {
                "key": "vfx.blur.abcdef12",
                "kind": "video_fx",
                "enabled": True,
                "tags": [],
                "params_mode": "defaults_only",
                "plugin_unique_id": "provider.blur",
            }
        ]
    }
    capabilities = _capabilities("apply_fx", questions=["VQ-04", "VQ-17"])
    result = compile_catalog_items(
        edl, _words(), _timeline(), catalog, capabilities, working_root=Path.cwd()
    )

    assert result.operations == [
        {
            "op": "apply_fx",
            "target_type": "event",
            "target_id": "e0",
            "catalog_key": "vfx.blur.abcdef12",
            "plugin_unique_id": "provider.blur",
            "params": {},
        }
    ]
    assert result.item_outcomes[0]["status"] == "applied"


def test_effect_rejects_unproven_parameter_mode() -> None:
    edl = {"effects": [{"at_event": "e0", "key": "vfx.blur.abcdef12", "reason": "test"}]}
    catalog = {
        "video_fx": [
            {
                "key": "vfx.blur.abcdef12",
                "kind": "video_fx",
                "enabled": True,
                "tags": [],
                "params_mode": "preset_only",
                "plugin_unique_id": "provider.blur",
            }
        ]
    }
    result = compile_catalog_items(
        edl,
        _words(),
        _timeline(),
        catalog,
        _capabilities("apply_fx", questions=["VQ-04", "VQ-17"]),
        working_root=Path.cwd(),
    )

    assert result.operations == []
    assert result.rejected_items[0]["code"] == "E_FX_PARAMETERS_UNPROVEN"


def test_transition_duration_uses_catalog_default_and_clamps_to_policy() -> None:
    from orchestrator.catalog_compiler import resolved_transition_duration

    config = CatalogPlacementConfig(minimum_transition_frames=3, maximum_transition_frames=8)

    assert resolved_transition_duration({"default_duration_frames": 1}, config) == 3
    assert resolved_transition_duration({"default_duration_frames": 20}, config) == 8


def test_disabled_transition_is_rejected_with_typed_code() -> None:
    edl = {
        "cuts": [{"id": "c0", "remove": {"from_word": "w1", "to_word": "w1"}}],
        "transitions": [
            {"at_cut": "c0", "offset_hint": "at", "type": "tr.fade.abcdef12", "reason": "test"}
        ],
    }
    catalog = {
        "transitions": [
            {
                "key": "tr.fade.abcdef12",
                "kind": "transition",
                "enabled": False,
                "tags": [],
                "allowed_contexts": ["continuous_speech"],
                "default_duration_frames": 2,
            }
        ]
    }

    result = compile_catalog_items(
        edl, _words(), _timeline(), catalog, empty_capabilities(), working_root=Path.cwd()
    )

    assert result.rejected_items[0]["code"] == "E_CATALOG_DISABLED"


def test_edl_schema_rejects_model_supplied_effect_parameters() -> None:
    import json

    from orchestrator.contracts import validate

    edl_path = Path("tests/fixtures/edl/valid_minimal.json")
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    edl["effects"] = [
        {
            "at_event": "e0",
            "key": "vfx.blur.abcdef12",
            "reason": "fixture",
            "params": {"radius": 5},
        }
    ]

    assert validate("edl", edl)


def test_edl_schema_rejects_planner_supplied_sfx_gain() -> None:
    import json

    from orchestrator.contracts import validate

    edl = json.loads(Path("tests/fixtures/edl/valid_minimal.json").read_text(encoding="utf-8"))
    edl["sfx"] = [
        {
            "at_word": "w1",
            "offset_hint": "at",
            "key": "sfx.whoosh.abcdef12",
            "reason": "fixture",
            "gain_db": -12,
        }
    ]

    assert validate("edl", edl)


def test_compile_report_carries_used_sfx_license(tmp_path: Path) -> None:
    from orchestrator.compiler import compile_edl
    from orchestrator.contracts import validate

    asset = tmp_path / "whoosh.wav"
    asset.write_bytes(b"synthetic fixture")
    words = {
        "words": [{"id": "w0", "start": 1.0, "end": 1.2, "speaker_key": "speaker_a"}],
        "gaps": [],
    }
    timeline = {
        "fps": "30/1",
        "duration_frames": 300,
        "source_hash": "sha256:" + "a" * 64,
        "tracks": [
            {"id": "a0", "kind": "audio", "index": 0},
            {"id": "v0", "kind": "video", "index": 0},
        ],
        "groups": [{"id": "lg0", "event_ids": ["e0", "e1"]}],
        "events": [
            {
                "id": "e0",
                "track_id": "a0",
                "group_id": "lg0",
                "start_frame": 0,
                "source_offset_frames": 0,
                "length_frames": 300,
            },
            {
                "id": "e1",
                "track_id": "v0",
                "group_id": "lg0",
                "start_frame": 0,
                "source_offset_frames": 0,
                "length_frames": 300,
            },
        ],
    }
    edl = {
        "cuts": [],
        "gap_actions": [],
        "transitions": [],
        "effects": [],
        "sfx": [
            {
                "at_word": "w0",
                "offset_hint": "at",
                "key": "sfx.whoosh.abcdef12",
                "reason": "fixture",
            }
        ],
    }
    catalog = {
        "sfx": [
            {
                "key": "sfx.whoosh.abcdef12",
                "kind": "sfx",
                "enabled": True,
                "tags": ["whoosh"],
                "params_mode": "defaults_only",
                "path": str(asset),
                "duration": 0.1,
                "loudness_lufs": -23.0,
                "peak_dbfs": -3.0,
                "license": "CC0-1.0",
                "source": "synthetic",
            }
        ]
    }
    samples = [0] * (3 * 48000)

    _ops, report, _intervals = compile_edl(
        edl,
        words,
        timeline,
        job_id="license",
        working_copy_path=str(tmp_path / "working.veg"),
        catalog=catalog,
        capabilities=_capabilities("add_audio_event", questions=["VQ-18"]),
        working_root=tmp_path,
        audio_samples=samples,
        sample_rate=48000,
    )

    assert report["sfx_used"] == [{"key": "sfx.whoosh.abcdef12", "license": "CC0-1.0"}]
    assert not validate("compile_report", report)
