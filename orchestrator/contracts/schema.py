"""Load JSON Schema documents and return safe validation issues."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from .errors import ErrorCode, ValidationIssue

_SCHEMA_NAMES = {"words", "speakers", "catalog", "edl", "ops", "config"}
_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
_SAFE_PATH_PART = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")


def load_schema(name: str) -> dict[str, Any]:
    """Load one authoritative schema; unknown names fail explicitly."""
    if name not in _SCHEMA_NAMES:
        raise ValueError("unknown schema name")
    schema_path = _SCHEMA_DIR / f"{name}.schema.json"
    with schema_path.open("r", encoding="utf-8") as schema_file:
        loaded: Any = json.load(schema_file)
    if not isinstance(loaded, dict):
        raise ValueError("schema root must be an object")
    return loaded


def validate(name: str, document: object) -> list[ValidationIssue]:
    """Validate a document without raising for invalid user or model data."""
    validator = Draft202012Validator(load_schema(name))
    issues: list[ValidationIssue] = []
    for error in validator.iter_errors(document):
        path_parts: list[str] = []
        for part in error.absolute_path:
            if isinstance(part, int):
                path_parts.append(f"[{part}]")
            elif _SAFE_PATH_PART.fullmatch(str(part)):
                path_parts.append(("." if path_parts else "$") + str(part))
            else:
                path_parts.append(".*")
        path = "".join(path_parts) or "$"
        issues.append(
            ValidationIssue(
                ErrorCode.E_SCHEMA,
                path,
                "document does not match the contract schema",
            )
        )
    return sorted(issues, key=lambda issue: (issue.path, issue.message))
