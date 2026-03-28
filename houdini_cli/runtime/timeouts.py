"""Central timeout defaults."""

from __future__ import annotations

import os


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


CONNECT_TIMEOUT_SECONDS = _env_float("HOUDINI_CLI_CONNECT_TIMEOUT", 5.0)
SYNC_REQUEST_TIMEOUT_SECONDS = _env_float("HOUDINI_CLI_SYNC_REQUEST_TIMEOUT", 20.0)
