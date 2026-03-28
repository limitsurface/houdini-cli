"""Error categorization helpers."""

from __future__ import annotations

from ..transport.rpyc import TransportConnectionError, TransportTimeoutError


def error_category(exc: Exception) -> str:
    if isinstance(exc, (TransportTimeoutError, TimeoutError)):
        return "timeout"
    if isinstance(exc, (TransportConnectionError, ConnectionError, OSError)):
        return "connection"
    if isinstance(exc, ValueError):
        return "argument"
    return "runtime"
