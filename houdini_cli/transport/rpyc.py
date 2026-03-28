"""RPyC transport helpers."""

from __future__ import annotations

import contextlib
import logging
import socket
from dataclasses import dataclass
from typing import Any

import rpyc
from rpyc.utils.classic import obtain

from ..runtime.timeouts import CONNECT_TIMEOUT_SECONDS, SYNC_REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HoudiniSession:
    connection: Any
    hou: Any


def localize(value: Any) -> Any:
    """Convert remote RPyC netrefs into local Python objects."""
    return obtain(value)


@contextlib.contextmanager
def connect(host: str, port: int) -> HoudiniSession:
    logger.debug("Connecting to Houdini at %s:%s", host, port)
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(CONNECT_TIMEOUT_SECONDS)
    try:
        conn = rpyc.classic.connect(host, port)
    finally:
        socket.setdefaulttimeout(old_timeout)

    if hasattr(conn, "_config"):
        conn._config["sync_request_timeout"] = SYNC_REQUEST_TIMEOUT_SECONDS

    try:
        yield HoudiniSession(connection=conn, hou=conn.modules.hou)
    finally:
        logger.debug("Closing Houdini connection")
        conn.close()
