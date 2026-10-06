"""Build child-process environments without propagating credentials."""

from __future__ import annotations

import os
from collections.abc import Mapping

_SECRET_NAME_MARKERS = (
    "API_KEY",
    "APIKEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "AUTH",
    "CREDENTIAL",
)
_PRIVATE_INDEX_NAMES = {"PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL"}


def safe_child_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Remove credential-shaped variables and custom package indexes from children."""
    environment = os.environ if source is None else source
    return {
        name: value
        for name, value in environment.items()
        if name.upper() not in _PRIVATE_INDEX_NAMES
        and not any(marker in name.upper() for marker in _SECRET_NAME_MARKERS)
    }
