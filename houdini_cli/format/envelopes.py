"""JSON result envelopes."""

from __future__ import annotations

from .errors import error_category


def success_result(data: dict, meta: dict | None = None) -> dict:
    result = {"ok": True, "data": data}
    if meta:
        result["meta"] = meta
    return result


def error_result(exc: Exception) -> dict:
    return {
        "ok": False,
        "error": {
            "category": error_category(exc),
            "type": f"{exc.__class__.__module__}.{exc.__class__.__name__}",
            "message": str(exc),
        },
    }
