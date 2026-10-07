"""Validation helpers for executor-reported operation capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orchestrator.contracts import validate

_CAPABILITY_EVIDENCE = {
    "add_transition": {"VQ-05", "VQ-06"},
    "add_audio_event": {"VQ-18"},
    "set_gain": {"VQ-18"},
    "apply_fx": {"VQ-04", "VQ-17"},
}


def empty_capabilities() -> dict[str, Any]:
    """Return the fail-closed default while no executor has E0 evidence."""
    return {
        "schema_version": "1.0.0",
        "executor_id": "none",
        "supported_operations": [],
        "verified_questions": [],
    }


def supported_operations(document: Mapping[str, Any]) -> tuple[set[str], list[str]]:
    """Return only operations whose schema and required VQ evidence are present."""
    if validate("capabilities", document):
        return set(), ["capabilities document failed schema validation"]
    operations = document.get("supported_operations", [])
    questions = set(document.get("verified_questions", []))
    enabled: set[str] = set()
    warnings: list[str] = []
    if not isinstance(operations, list):
        return set(), ["capabilities operation list is invalid"]
    for operation in operations:
        required = _CAPABILITY_EVIDENCE.get(str(operation), set())
        if required <= questions:
            enabled.add(str(operation))
        else:
            warnings.append("operation capability is missing required VQ evidence")
    return enabled, warnings
