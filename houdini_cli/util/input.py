"""Shared file and standard-input readers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO


def _read_source(source: str, *, stdin: TextIO | None = None) -> tuple[str, str]:
    if source == "-":
        text = (stdin or sys.stdin).read()
        label = "stdin"
    else:
        path = Path(source)
        text = path.read_text(encoding="utf-8")
        label = str(path)
    if not text:
        raise ValueError(f"Input from {label} is empty")
    return text, label


def read_text_input(source: str, *, stdin: TextIO | None = None) -> str:
    """Read non-empty UTF-8 text from a path or '-' for stdin."""
    text, _ = _read_source(source, stdin=stdin)
    return text


def read_json_input(source: str, *, stdin: TextIO | None = None) -> Any:
    """Read JSON from a UTF-8 path or '-' for stdin."""
    text, label = _read_source(source, stdin=stdin)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON from {label} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
