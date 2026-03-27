"""RPyC transport helpers."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any

import rpyc
from rpyc.utils.classic import obtain

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
    conn = rpyc.classic.connect(host, port)
    try:
        yield HoudiniSession(connection=conn, hou=conn.modules.hou)
    finally:
        logger.debug("Closing Houdini connection")
        conn.close()
