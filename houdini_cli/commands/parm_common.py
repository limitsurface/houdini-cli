"""Shared parameter command helpers."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize


def get_parm(session: Any, parm_path: str) -> Any:
    parm = session.hou.parm(parm_path)
    if parm is None:
        raise ValueError(f"Parameter not found: {parm_path}")
    return parm


def get_parm_tuple(session: Any, parm_path: str) -> Any:
    parm_tuple = session.hou.parmTuple(parm_path)
    if parm_tuple is not None:
        return parm_tuple
    parm = get_parm(session, parm_path)
    parm_tuple = parm.tuple()
    if len(parm_tuple) <= 1:
        raise ValueError(f"Parameter is not a tuple: {parm_path}")
    return parm_tuple


def tuple_members(parm: Any) -> list[Any]:
    return list(parm.tuple())


def tuple_name(parm: Any) -> str:
    return localize(parm.tuple().name())


def is_tuple_component(parm: Any) -> bool:
    members = tuple_members(parm)
    return len(members) > 1 and localize(parm.name()) != tuple_name(parm)


def component_value(parm: Any) -> Any:
    data = localize(parm.valueAsData())
    members = tuple_members(parm)
    if not (is_tuple_component(parm) and isinstance(data, list) and len(data) == len(members)):
        return data
    names = [localize(item.name()) for item in members]
    return data[names.index(localize(parm.name()))]


def parse_cli_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw
