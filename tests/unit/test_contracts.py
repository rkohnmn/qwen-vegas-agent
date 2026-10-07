from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from orchestrator.contracts import (
    ConfigError,
    ErrorCode,
    RedactingFilter,
    catalog_summary,
    check_catalog,
    check_compile_report,
    check_edl_against,
    check_ops,
    check_run_manifest,
    check_timeline,
    check_verify_report,
    check_words,
    hash_words,
    load_config,
    load_schema,
    redact,
    validate,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
SECRET = "milestone0-test-secret"


def load_fixture(contract: str, name: str) -> dict[str, Any]:
    path = FIXTURES / contract / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def references() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_fixture("words", "valid_realistic"),
        load_fixture("speakers", "valid_realistic"),
        load_fixture("catalog", "valid_realistic"),
    )


def codes(issues: list[Any]) -> set[ErrorCode]:
    return {issue.code for issue in issues}


@pytest.mark.parametrize("name", ["words", "speakers", "catalog", "edl", "ops", "config"])
def test_all_json_schemas_are_valid_2020_12(name: str) -> None:
    Draft202012Validator.check_schema(load_schema(name))


@pytest.mark.parametrize(
    ("contract", "name"),
    [
        ("words", "valid_minimal"),
        ("words", "valid_realistic"),
        ("speakers", "valid_minimal"),
        ("speakers", "valid_realistic"),
        ("catalog", "valid_minimal"),
        ("catalog", "valid_realistic"),
        ("edl", "valid_minimal"),
        ("edl", "valid_realistic"),
        ("ops", "valid_minimal"),
        ("ops", "valid_realistic"),
        ("timeline", "valid_minimal"),
        ("compile_report", "valid_minimal"),
        ("verify_report", "valid_minimal"),
        ("run_manifest", "valid_minimal"),
    ],
)
def test_valid_fixtures_match_schema(contract: str, name: str) -> None:
    assert validate(contract, load_fixture(contract, name)) == []


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("invalid_end_before_start", ErrorCode.E_WORD_TIME),
        ("invalid_duplicate_id", ErrorCode.E_DUPLICATE_ID),
        ("invalid_missing_segment_word", ErrorCode.E_REF_WORD),
    ],
)
def test_words_semantic_fixtures_return_codes(name: str, expected: ErrorCode) -> None:
    issues = check_words(load_fixture("words", name))
    assert expected in codes(issues)


def test_words_times_are_monotonic() -> None:
    words = load_fixture("words", "valid_realistic")
    words["words"][1]["start"] = words["words"][0]["start"] - 0.1
    assert ErrorCode.E_WORD_ORDER in codes(check_words(words))


def test_edl_referential_fixture_codes() -> None:
    words, speakers, catalog = references()
    expectations = {
        "invalid_unknown_catalog": ErrorCode.E_REF_CATALOG,
        "invalid_unknown_word": ErrorCode.E_REF_WORD,
        "invalid_words_hash_mismatch": ErrorCode.E_WORDS_HASH,
        "invalid_unknown_segment": ErrorCode.E_REF_SEGMENT,
        "invalid_unknown_gap": ErrorCode.E_REF_GAP,
        "invalid_unknown_speaker": ErrorCode.E_REF_SPEAKER,
        "invalid_overlapping_cuts": ErrorCode.E_CUT_OVERLAP,
        "invalid_reversed_cut": ErrorCode.E_CUT_ORDER,
        "invalid_unknown_gap_action": ErrorCode.E_REF_GAP,
    }
    for name, expected in expectations.items():
        edl = load_fixture("edl", name)
        assert validate("edl", edl) == []
        assert expected in codes(check_edl_against(edl, words, speakers, catalog))


def test_new_timeline_and_report_semantics_are_checked() -> None:
    timeline = load_fixture("timeline", "invalid_missing_group_event")
    assert ErrorCode.E_REF_EVENT in codes(check_timeline(timeline))

    compile_report = load_fixture("compile_report", "invalid_percentage_mismatch")
    assert ErrorCode.E_REPORT_CONSISTENCY in codes(check_compile_report(compile_report))

    verify_report = load_fixture("verify_report", "invalid_missing_fix")
    assert ErrorCode.E_REPORT_CONSISTENCY in codes(check_verify_report(verify_report))

    manifest = load_fixture("run_manifest", "invalid_integrity_mismatch")
    assert ErrorCode.E_MANIFEST_INTEGRITY in codes(check_run_manifest(manifest))


def test_run_manifest_file_hash_mismatch_is_detected() -> None:
    manifest = load_fixture("run_manifest", "valid_minimal")
    manifest["source_integrity"]["files"][0]["unchanged"] = False
    assert ErrorCode.E_MANIFEST_INTEGRITY in codes(check_run_manifest(manifest))


def test_edl_gap_actions_require_unique_cut_and_gap_ids() -> None:
    words, speakers, catalog = references()
    edl = load_fixture("edl", "valid_realistic")
    edl["gap_actions"][0]["id"] = edl["cuts"][0]["id"]
    assert ErrorCode.E_DUPLICATE_ID in codes(check_edl_against(edl, words, speakers, catalog))

    edl = load_fixture("edl", "valid_realistic")
    edl["gap_actions"].append({**edl["gap_actions"][0], "id": "c3"})
    assert ErrorCode.E_DUPLICATE_ID in codes(check_edl_against(edl, words, speakers, catalog))


def test_catalog_duplicate_key_is_rejected() -> None:
    catalog = load_fixture("catalog", "invalid_duplicate_key")
    assert validate("catalog", catalog) == []
    assert ErrorCode.E_DUPLICATE_CATALOG_KEY in codes(check_catalog(catalog))


def test_ops_path_confinement_and_creation_order() -> None:
    escaped = load_fixture("ops", "invalid_path_outside_workdir")
    assert validate("ops", escaped) == []
    assert ErrorCode.E_PATH_CONFINEMENT in codes(check_ops(escaped, FIXTURES))

    future = load_fixture("ops", "invalid_future_reference")
    assert validate("ops", future) == []
    assert ErrorCode.E_OP_ORDER in codes(check_ops(future, FIXTURES))


def test_ops_requires_nonnegative_integer_frames() -> None:
    ops = load_fixture("ops", "valid_minimal")
    ops["operations"][0]["frame"] = 1.5
    assert ErrorCode.E_FRAME_TYPE in codes(check_ops(ops, FIXTURES))
    ops["operations"][0]["frame"] = -1
    assert ErrorCode.E_FRAME_TYPE in codes(check_ops(ops, FIXTURES))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timestamp", 12.4),
        ("color", "#010203"),
        ("plugin_unique_id", "{private-plugin-id}"),
        ("file_path", "private/asset.wav"),
    ],
)
def test_edl_rejects_resolved_or_private_fields(field: str, value: object) -> None:
    edl = load_fixture("edl", "valid_minimal")
    edl[field] = value
    assert ErrorCode.E_SCHEMA in codes(validate("edl", edl))


def test_catalog_summary_is_allowlisted() -> None:
    catalog = load_fixture("catalog", "valid_realistic")
    summary = catalog_summary(catalog)
    encoded = json.dumps(summary, sort_keys=True)
    assert "plugin_unique_id" not in encoded
    assert "{fixture-" not in encoded
    assert "whoosh_01.wav" not in encoded
    assert "assets/" not in encoded
    assert all("key" in entry and "kind" in entry for entry in summary["entries"])


def test_hash_is_stable_under_object_key_reordering() -> None:
    words = load_fixture("words", "valid_realistic")
    reordered = dict(reversed(list(words.items())))
    assert hash_words(words) == hash_words(reordered)
    reordered["speaker_mode"] = "single"
    assert hash_words(words) != hash_words(reordered)


def test_config_example_is_secret_free_and_dry_run_by_default() -> None:
    config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    assert validate("config", config) == []
    assert config["mode"] == "dry-run"
    assert config["llm"]["endpoint"] == "https://<tailnet-host>.ts.net/v1"
    assert "api_key" not in config["llm"]
    assert SECRET not in json.dumps(config)


def test_config_loader_keeps_explicit_key_only_in_memory(tmp_path: Path) -> None:
    config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    loaded = load_config(config_path, {"QWEN_VEGAS_API_KEY": SECRET})
    assert loaded["llm"]["api_key"] == SECRET
    assert "api_key" not in json.loads(config_path.read_text(encoding="utf-8"))["llm"]


def test_config_errors_do_not_echo_secret_or_path(tmp_path: Path) -> None:
    config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    config["llm"]["api_key"] = SECRET
    config["llm"]["endpoint"] = "invalid"
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ConfigError) as raised:
        load_config(config_path)
    assert SECRET not in str(raised.value)
    assert str(tmp_path) not in str(raised.value)


def test_redaction_covers_values_fields_and_log_records() -> None:
    redacted = redact(
        {
            "message": f"Authorization: Bearer {SECRET}; api_key={SECRET}",
            "api_key": SECRET,
        },
        [SECRET],
    )
    assert SECRET not in json.dumps(redacted)
    assert "[REDACTED]" in json.dumps(redacted)

    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.addFilter(RedactingFilter([SECRET]))
    logger = logging.getLogger(f"redaction-test-{id(output)}")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    logger.error("request failed Authorization: Bearer %s api_key=%s", SECRET, SECRET)
    handler.flush()
    assert SECRET not in output.getvalue()
    assert "[REDACTED]" in output.getvalue()


def test_gitignore_covers_secrets_work_data_media_and_build_outputs() -> None:
    rules = (ROOT / ".gitignore").read_text(encoding="utf-8")
    required = [
        "config.json",
        "config.local.json",
        ".env*",
        "voices/",
        "cache/",
        "runs/",
        "*.veg.bak",
        "*.mp4",
        "*.mkv",
        "*.mov",
        "*.wav",
        "!assets/**/*.mp4",
        "!tests/fixtures/**/*.wav",
        "__pycache__/",
        ".venv/",
        "bin/",
        "obj/",
        "*.dll",
        "*.pdb",
        "*.key",
        "*.pem",
    ]
    for rule in required:
        assert rule in rules


def test_repo_examples_have_no_personal_paths_hosts_or_real_keys() -> None:
    secret_patterns = [
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+-]{32,}"),
        re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*[\"']?[A-Za-z0-9._~+-]{32,}"),
        re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+"),
        re.compile(r"(?i)" + "/" + "home/" + r"[^/\s]+"),
    ]
    skipped_parts = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".pytest-temp",
        "config.local.json",
    }
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(
            part in skipped_parts or part.startswith(".pytest-temp-") for part in path.parts
        ):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in secret_patterns:
            assert not pattern.search(content), f"possible secret or personal path in {path.name}"
        for match in re.finditer(r"https?://([^/\s\"'<>]+)", content):
            host = match.group(1).lower()
            if host.endswith(".ts.net"):
                assert host == "<tailnet-host>.ts.net", (
                    f"non-placeholder tailnet host in {path.name}"
                )


def test_run_manifest_records_only_licensed_sfx() -> None:
    manifest = load_fixture("run_manifest", "valid_sfx_used")
    assert not validate("run_manifest", manifest)
    assert not check_run_manifest(manifest)

    manifest["sfx_used"][0]["license"] = "UNLICENSED"
    assert ErrorCode.E_REPORT_CONSISTENCY in codes(check_run_manifest(manifest))
