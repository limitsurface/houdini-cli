"""Bounded, expression-aware parameter value projection helpers."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize
from .parm_common import tuple_members, tuple_name


SCALAR_TYPES = (bool, int, float)


def parm_template_type(parm: Any) -> str:
    return localize(parm.parmTemplate().type().name())


def parm_display_name(parm: Any) -> str:
    members = tuple_members(parm)
    return tuple_name(parm) if len(members) > 1 else localize(parm.name())


def parm_type_label(parm: Any) -> str:
    members = tuple_members(parm)
    base = parm_template_type(parm)
    return f"{base}{len(members)}" if len(members) > 1 else base


def parm_is_default(parm: Any) -> bool:
    return all(bool(localize(member.isAtDefault())) for member in tuple_members(parm))


def parm_expressions(parm: Any, *, max_items: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total = 0
    for member in tuple_members(parm):
        keyframes_method = getattr(member, "keyframes", None)
        if not callable(keyframes_method):
            continue
        try:
            keyframes = list(keyframes_method())
        except Exception:
            continue
        if not keyframes:
            continue
        total += 1
        if len(rows) >= max_items:
            continue
        try:
            text = localize(member.expression())
        except Exception:
            text = None
        try:
            language = str(localize(member.expressionLanguage())).rsplit(".", 1)[-1]
        except Exception:
            language = None
        rows.append({"parm": localize(member.name()), "language": language, "text": text})
    return {
        "count": total,
        "items": rows,
        "truncated": total > len(rows),
    }


def _bounded_sequence(value: Any, *, max_items: int) -> dict[str, Any]:
    items = list(localize(value))
    return {
        "kind": "sequence",
        "item_count": len(items),
        "items": items[:max_items],
        "truncated": len(items) > max_items,
    }


def _ramp_summary(parm: Any, *, max_items: int) -> dict[str, Any]:
    ramp = parm.eval()
    keys = list(localize(ramp.keys()))
    bases = [str(localize(item)).rsplit(".", 1)[-1].lower() for item in ramp.basis()]
    unique_bases = list(dict.fromkeys(bases))
    return {
        "kind": "ramp",
        "point_count": len(keys),
        "basis": unique_bases[:max_items],
        "basis_truncated": len(unique_bases) > max_items,
    }


def parm_value(parm: Any, *, mode: str, max_items: int) -> Any:
    if mode == "none":
        return None

    template_type = parm_template_type(parm)
    if template_type == "Ramp":
        return _ramp_summary(parm, max_items=max_items) if mode in {"scalar", "summary"} else localize(parm.valueAsData())

    instances_method = getattr(parm, "multiParmInstances", None)
    if callable(instances_method):
        try:
            instances = list(instances_method())
        except Exception:
            instances = []
        if instances:
            return {
                "kind": "multiparm",
                "instance_count": len(instances),
            }

    value = localize(parm.valueAsData())
    members = tuple_members(parm)
    if mode == "full":
        return value
    if isinstance(value, str):
        if mode == "scalar" and len(value) <= 120:
            return value
        return {
            "kind": "string",
            "length": len(value),
            "preview": value[: min(120, max_items * 20)],
            "truncated": len(value) > min(120, max_items * 20),
        }
    if isinstance(value, SCALAR_TYPES):
        return value
    if isinstance(value, (list, tuple)):
        if mode == "scalar" and len(members) <= 4 and len(value) <= 4:
            return value
        return _bounded_sequence(value, max_items=max_items)
    if isinstance(value, dict):
        keys = list(value.keys())
        return {
            "kind": "mapping",
            "item_count": len(keys),
            "keys": keys[:max_items],
            "truncated": len(keys) > max_items,
        }
    return {"kind": template_type.lower(), "type": type(value).__name__}


def parm_projection_item(parm: Any, *, mode: str, max_items: int, display_name: str | None = None) -> dict[str, Any]:
    item = {
        "p": display_name or parm_display_name(parm),
        "t": parm_type_label(parm),
        "v": parm_value(parm, mode=mode, max_items=max_items),
        "default": parm_is_default(parm),
    }
    if mode != "none":
        expressions = parm_expressions(parm, max_items=max_items)
        if expressions["count"]:
            item["expressions"] = expressions
    return item


def bounded_parm_row(parm: Any, *, mode: str, max_items: int = 10) -> list[Any]:
    item = parm_projection_item(parm, mode=mode, max_items=max_items)
    value = item["v"]
    expressions = item.get("expressions")
    if expressions:
        if isinstance(value, dict):
            value = {**value, "expressions": expressions}
        else:
            value = {"kind": "evaluated_expression", "value": value, "expressions": expressions}
    return [item["p"], item["t"], value, "" if item["default"] else "n"]
