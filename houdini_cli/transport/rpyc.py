"""RPyC transport helpers."""

from __future__ import annotations

import contextlib
import logging
import socket
from dataclasses import dataclass
from typing import Any

import rpyc
from rpyc.core.async_ import AsyncResultTimeout
from rpyc.utils.classic import obtain

from ..runtime.timeouts import CONNECT_TIMEOUT_SECONDS, SYNC_REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HoudiniSession:
    connection: Any
    hou: Any


class TransportConnectionError(ConnectionError):
    """Connection to Houdini failed."""


class TransportTimeoutError(TimeoutError):
    """A remote Houdini request exceeded the configured timeout."""


def localize(value: Any) -> Any:
    """Convert remote RPyC netrefs into local Python objects."""
    try:
        return obtain(value)
    except AsyncResultTimeout as exc:
        raise TransportTimeoutError("Timed out while retrieving remote Houdini data") from exc


@contextlib.contextmanager
def sync_request_timeout(session: HoudiniSession, seconds: float):
    connection = getattr(session, "connection", None)
    config = getattr(connection, "_config", None)
    if config is None:
        yield
        return

    previous = config.get("sync_request_timeout")
    config["sync_request_timeout"] = seconds
    try:
        yield
    finally:
        config["sync_request_timeout"] = previous


def _connect_error_message(host: str, port: int, exc: Exception) -> str:
    detail = str(exc).strip()
    base = f"Failed to connect to Houdini at {host}:{port}"
    return f"{base}: {detail}" if detail else base


@contextlib.contextmanager
def connect(host: str, port: int, *, sync_request_timeout_seconds: float | None = None) -> HoudiniSession:
    logger.debug("Connecting to Houdini at %s:%s", host, port)
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(CONNECT_TIMEOUT_SECONDS)
    try:
        try:
            conn = rpyc.classic.connect(host, port)
        except (socket.timeout, ConnectionRefusedError, EOFError, OSError) as exc:
            raise TransportConnectionError(_connect_error_message(host, port, exc)) from exc
    finally:
        socket.setdefaulttimeout(old_timeout)

    if hasattr(conn, "_config"):
        conn._config["sync_request_timeout"] = (
            sync_request_timeout_seconds
            if sync_request_timeout_seconds is not None
            else SYNC_REQUEST_TIMEOUT_SECONDS
        )

    try:
        try:
            yield HoudiniSession(connection=conn, hou=conn.modules.hou)
        except AsyncResultTimeout as exc:
            raise TransportTimeoutError("Timed out while waiting for Houdini to respond") from exc
    finally:
        logger.debug("Closing Houdini connection")
        conn.close()
