"""Node parameter discovery commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..remote.node_parms import NODE_PARMS_REMOTE
from ..transport.rpyc import connect, localize
from .parm_common import tuple_members, tuple_name
from .node_parm_values import bounded_parm_row


SKIPPED_TEMPLATE_TYPES = {"Button", "Folder", "FolderSet", "Label", "Separator"}


def get_node(session: Any, node_path: str) -> Any:
    node = session.hou.node(node_path)
    if node is None:
        raise ValueError(f"Node not found: {node_path}")
    return node


def parm_template_type(parm: Any) -> str:
    return localize(parm.parmTemplate().type().name())


def tuple_type_label(parm: Any) -> str:
    members = tuple_members(parm)
    base = parm_template_type(parm)
    return f"{base}{len(members)}" if len(members) > 1 else base


def parm_flags(parm: Any) -> str:
    members = tuple_members(parm)
    return "".join(["n" if any(not bool(localize(item.isAtDefault())) for item in members) else ""])


def parm_display_name(parm: Any) -> str:
    members = tuple_members(parm)
    return tuple_name(parm) if len(members) > 1 else localize(parm.name())


def parm_row_value(parm: Any, *, full_values: bool = False) -> Any:
    members = tuple_members(parm)
    data = localize(parm.valueAsData())
    if not full_values and isinstance(data, str) and len(data) > 120:
        return data[:117] + "..."
    return data if len(members) > 1 else data


def parm_row(parm: Any, *, full_values: bool = False) -> list[Any]:
    return [
        parm_display_name(parm),
        tuple_type_label(parm),
        parm_row_value(parm, full_values=full_values),
        parm_flags(parm),
    ]


def iter_discoverable_parms(node: Any) -> list[Any]:
    rows: list[Any] = []
    seen: set[str] = set()
    for parm in node.parms():
        if parm_template_type(parm) in SKIPPED_TEMPLATE_TYPES:
            continue
        key = localize(parm.path())
        members = tuple_members(parm)
        if len(members) > 1:
            key = localize(members[0].path())
        if key in seen:
            continue
        seen.add(key)
        rows.append(parm)
    return rows


def matches_parm(parm: Any, *, name: str | None, parm_type: str | None, non_default: bool) -> bool:
    if non_default and bool(localize(parm.isAtDefault())):
        members = tuple_members(parm)
        if all(bool(localize(item.isAtDefault())) for item in members):
            return False
    if name:
        needle = name.lower()
        names = [parm_display_name(parm), *[localize(item.name()) for item in tuple_members(parm)]]
        lowered = [item.lower() for item in names]
        exact = any(item == needle for item in lowered)
        prefix = any(item.startswith(needle) for item in lowered)
        partial = len(needle) >= 3 and any(needle in item for item in lowered)
        if not (exact or prefix or partial):
            return False
    if parm_type and tuple_type_label(parm) != parm_type:
        return False
    return True


def node_parm_rows_in_houdini(
    session: Any,
    node_path: str,
    *,
    name: str | None,
    parm_type: str | None,
    non_default: bool,
    full_values: bool,
    max_parms: int,
) -> list[list[Any]]:
    if not hasattr(session, "connection"):
        node = get_node(session, node_path)
        return [
            parm_row(parm, full_values=full_values)
            for parm in iter_discoverable_parms(node)
            if matches_parm(parm, name=name, parm_type=parm_type, non_default=non_default)
        ][:max_parms]

    return localize(
        NODE_PARMS_REMOTE.evaluate(
            session.connection,
            "rows",
            node_path,
            name,
            parm_type,
            bool(non_default),
            bool(full_values),
            int(max_parms),
        )
    )


def bounded_node_parm_rows_in_houdini(
    session: Any,
    node_path: str,
    *,
    name: str | None,
    parm_type: str | None,
    non_default: bool,
    value_mode: str,
    max_parms: int,
    max_items: int = 10,
) -> dict[str, Any]:
    if not hasattr(session, "connection"):
        node = get_node(session, node_path)
        matches = [
            parm
            for parm in iter_discoverable_parms(node)
            if matches_parm(parm, name=name, parm_type=parm_type, non_default=non_default)
        ]
        rows = [
            bounded_parm_row(parm, mode=value_mode, max_items=max_items)
            for parm in matches[:max_parms]
        ]
        return {"rows": rows, "total": len(matches), "truncated": len(matches) > len(rows)}

    return localize(
        NODE_PARMS_REMOTE.evaluate(
            session.connection,
            "bounded_rows",
            node_path,
            name,
            parm_type,
            bool(non_default),
            value_mode,
            int(max_parms),
            int(max_items),
        )
    )


def _validate_discovery_args(args: argparse.Namespace) -> None:
    if args.max_parms < 1:
        raise ValueError("max parms must be at least one")
    if getattr(args, "full_values", False) and getattr(args, "value_mode", None) is not None:
        raise ValueError("--full-values cannot be combined with --value-mode")


def _discovery_payload(
    session: Any,
    args: argparse.Namespace,
    *,
    name: str | None,
    parm_type: str | None,
) -> tuple[list[list[Any]], dict[str, Any] | None]:
    value_mode = getattr(args, "value_mode", None)
    if value_mode is None:
        rows = node_parm_rows_in_houdini(
            session,
            args.node_path,
            name=name,
            parm_type=parm_type,
            non_default=args.non_default,
            full_values=getattr(args, "full_values", False),
            max_parms=args.max_parms,
        )
        return rows, None
    bounded = bounded_node_parm_rows_in_houdini(
        session,
        args.node_path,
        name=name,
        parm_type=parm_type,
        non_default=args.non_default,
        value_mode=value_mode,
        max_parms=args.max_parms,
    )
    return bounded["rows"], {
        "value_mode": value_mode,
        "total": int(bounded["total"]),
        "truncated": bool(bounded["truncated"]),
        "max_parms": args.max_parms,
    }


def handle_node_parms_list(args: argparse.Namespace) -> dict:
    _validate_discovery_args(args)
    with connect(args.host, args.port) as session:
        rows, meta = _discovery_payload(
            session,
            args,
            name=getattr(args, "name", None),
            parm_type=getattr(args, "parm_type", None),
        )
        return success_result(
            {
                "node": args.node_path,
                "count": len(rows),
                "cols": ["p", "t", "v", "f"],
                "rows": rows,
            },
            meta=meta,
        )


def handle_node_parms_find(args: argparse.Namespace) -> dict:
    _validate_discovery_args(args)
    with connect(args.host, args.port) as session:
        rows, meta = _discovery_payload(session, args, name=args.name, parm_type=args.parm_type)
        return success_result(
            {
                "node": args.node_path,
                "query": {
                    key: value
                    for key, value in {
                        "name": args.name,
                        "type": args.parm_type,
                        "non_default": True if args.non_default else None,
                    }.items()
                    if value is not None
                },
                "count": len(rows),
                "cols": ["p", "t", "v", "f"],
                "rows": rows,
            },
            meta=meta,
        )
