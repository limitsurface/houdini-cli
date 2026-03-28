"""Central timeout defaults."""

from __future__ import annotations

import os


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


CONNECT_TIMEOUT_SECONDS = _env_float("HOUDINI_CLI_CONNECT_TIMEOUT", 5.0)
SYNC_REQUEST_TIMEOUT_SECONDS = _env_float("HOUDINI_CLI_SYNC_REQUEST_TIMEOUT", 20.0)
EVAL_TIMEOUT_SECONDS = _env_float("HOUDINI_CLI_EVAL_TIMEOUT", 20.0)
TRAVERSAL_TIMEOUT_SECONDS = _env_float("HOUDINI_CLI_TRAVERSAL_TIMEOUT", 20.0)
BROAD_READ_TIMEOUT_SECONDS = _env_float("HOUDINI_CLI_BROAD_READ_TIMEOUT", 20.0)
