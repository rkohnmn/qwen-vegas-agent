"""Load the orchestrator config and redact configured secrets from logs."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .schema import validate

_AUTH_RE = re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+")
_KEY_RE = re.compile(r"(?i)((?:api[_-]?key|token|secret)\s*[:=]\s*)[^\s,;]+")
_SECRET_FIELD_NAMES = {"api_key", "apikey", "authorization", "token", "secret", "hf_token"}


class ConfigError(ValueError):
    """Expected config-load or validation failure with a safe message."""


def redact(value: Any, secrets: Sequence[str] = ()) -> Any:
    """Redact exact configured secrets and credential-shaped log text."""
    if isinstance(value, str):
        cleaned = _AUTH_RE.sub(r"\1[REDACTED]", value)
        cleaned = _KEY_RE.sub(r"\1[REDACTED]", cleaned)
        for secret in sorted((item for item in secrets if item), key=len, reverse=True):
            cleaned = cleaned.replace(secret, "[REDACTED]")
        return cleaned
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]"
            if str(key).lower() in _SECRET_FIELD_NAMES
            else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact(item, secrets) for item in value)
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    return value


class RedactingFilter(logging.Filter):
    """Logging filter that sanitizes message text and structured arguments."""

    def __init__(self, secrets: Sequence[str] = ()) -> None:
        super().__init__()
        self._secrets = tuple(secrets)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except (TypeError, ValueError):
            rendered = "log message unavailable"
        record.msg = str(redact(rendered, self._secrets))
        record.args = ()
        if record.exc_info is not None:
            exception_text = logging.Formatter().formatException(record.exc_info)
            record.msg += "\n" + str(redact(exception_text, self._secrets))
            record.exc_info = None
        return True


def load_config(
    path: str | Path = "config.json",
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Load validated config; an explicit key env var stays in orchestrator memory."""
    config_path = Path(path)
    if config_path.name != "config.json":
        raise ConfigError("config path must name config.json")
    if not config_path.is_file():
        raise ConfigError("config file is missing")
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            loaded: Any = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        raise ConfigError("config file could not be read") from None
    issues = validate("config", loaded)
    if issues:
        raise ConfigError("config does not match its schema")
    if not isinstance(loaded, dict):
        raise ConfigError("config must be an object")
    result = dict(loaded)
    result["llm"] = dict(result["llm"])
    environment = os.environ if environ is None else environ
    explicit_key = environment.get("QWEN_VEGAS_API_KEY", "")
    if explicit_key:
        result["llm"]["api_key"] = explicit_key
    return result
