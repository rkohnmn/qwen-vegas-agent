"""Canonical hashing for a words contract."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_words(words: dict[str, Any]) -> str:
    """Hash canonical UTF-8 JSON; object keys sort, array order is preserved."""
    canonical = json.dumps(
        words,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
