"""Safe, structured validation errors shared by contract checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable error codes returned by schema and referential validators."""

    E_SCHEMA = "E_SCHEMA"
    E_WORDS_HASH = "E_WORDS_HASH"
    E_REF_WORD = "E_REF_WORD"
    E_REF_SEGMENT = "E_REF_SEGMENT"
    E_REF_GAP = "E_REF_GAP"
    E_REF_SPEAKER = "E_REF_SPEAKER"
    E_REF_CATALOG = "E_REF_CATALOG"
    E_CUT_ORDER = "E_CUT_ORDER"
    E_CUT_OVERLAP = "E_CUT_OVERLAP"
    E_PATH_CONFINEMENT = "E_PATH_CONFINEMENT"
    E_FRAME_TYPE = "E_FRAME_TYPE"
    E_DUPLICATE_ID = "E_DUPLICATE_ID"
    E_DUPLICATE_CATALOG_KEY = "E_DUPLICATE_CATALOG_KEY"
    E_WORD_TIME = "E_WORD_TIME"
    E_WORD_ORDER = "E_WORD_ORDER"
    E_OP_ORDER = "E_OP_ORDER"
    E_REF_CUT = "E_REF_CUT"
    E_REF_EVENT = "E_REF_EVENT"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A model-safe validation failure; messages never include raw values."""

    code: ErrorCode
    path: str
    message: str
