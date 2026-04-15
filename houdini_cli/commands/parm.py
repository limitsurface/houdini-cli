"""Parameter commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.jsonio import load_json_input


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parm_parser = subparsers.add_parser("parm", help="Inspect and modify parameters.")
    parm_subparsers = parm_parser.add_subparsers(dest="parm_command", required=True)

    get_parser = parm_subparsers.add_parser("get", help="Get parameter value data.")
    get_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    get_parser.set_defaults(handler=handle_get)

    full_parser = parm_subparsers.add_parser("full", help="Get full structured parameter data.")
    full_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    full_parser.set_defaults(handler=handle_full)

    menu_parser = parm_subparsers.add_parser("menu", help="Get menu tokens and labels for a parameter.")
    menu_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    menu_parser.set_defaults(handler=handle_menu)

    set_parser = parm_subparsers.add_parser("set", help="Set a scalar or single string parameter value.")
    set_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    set_parser.add_argument("value", help="Parameter value.")
    set_parser.set_defaults(handler=handle_set)

    tuple_set_parser = parm_subparsers.add_parser("tuple-set", help="Set tuple parameter values.")
    tuple_set_parser.add_argument("parm_path", help="Tuple parameter path.")
    tuple_set_parser.add_argument("values", nargs="+", help="Tuple component values in order.")
    tuple_set_parser.set_defaults(handler=handle_tuple_set)

    text_set_parser = parm_subparsers.add_parser("text-set", help="Set a text parameter from stdin or a file.")
    text_set_parser.add_argument("parm_path", help="Parameter path.")
    text_set_parser.add_argument("--input", required=True, help="File path or '-' to read from stdin.")
    text_set_parser.set_defaults(handler=handle_text_set)

    full_set_parser = parm_subparsers.add_parser("full-set", help="Apply full structured parameter data.")
    full_set_parser.add_argument("parm_path", help="Parameter path.")
    full_set_parser.add_argument("--input", required=True, help="File path or '-' to read JSON from stdin.")
    full_set_parser.set_defaults(handler=handle_full_set)


def register_node_parms_parser(node_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parms_parser = node_subparsers.add_parser("parms", help="Discover parameters on one node.")
    parms_subparsers = parms_parser.add_subparsers(dest="node_parms_command", required=True)

    list_parser = parms_subparsers.add_parser("list", help="List parameters on one node.")
    list_parser.add_argument("node_path", help="Node path to inspect.")
    list_parser.add_argument("--non-default", action="store_true", help="Only include non-default parameters.")
    list_parser.add_argument("--max-parms", type=int, default=100, help="Maximum parameters to return.")
    list_parser.set_defaults(handler=handle_node_parms_list)

    find_parser = parms_subparsers.add_parser("find", help="Search parameters on one node.")
    find_parser.add_argument("node_path", help="Node path to inspect.")
    find_parser.add_argument("--name", help="Case-insensitive partial parm name match.")
    find_parser.add_argument("--type", dest="parm_type", help="Exact parm template type match.")
    find_parser.add_argument("--non-default", action="store_true", help="Only include non-default parameters.")
    find_parser.add_argument("--max-parms", type=int, default=100, help="Maximum parameters to return.")
    find_parser.set_defaults(handler=handle_node_parms_find)


def _get_parm(session: Any, parm_path: str) -> Any:
    parm = session.hou.parm(parm_path)
    if parm is None:
        raise ValueError(f"Parameter not found: {parm_path}")
    return parm


def _get_parm_tuple(session: Any, parm_path: str) -> Any:
    parm_tuple = session.hou.parmTuple(parm_path)
    if parm_tuple is not None:
        return parm_tuple
    parm = _get_parm(session, parm_path)
    parm_tuple = parm.tuple()
    if len(parm_tuple) <= 1:
        raise ValueError(f"Parameter is not a tuple: {parm_path}")
    return parm_tuple


def _tuple_members(parm: Any) -> list[Any]:
    return list(parm.tuple())


def _tuple_name(parm: Any) -> str:
    return localize(parm.tuple().name())


def _is_tuple_component(parm: Any) -> bool:
    members = _tuple_members(parm)
    return len(members) > 1 and localize(parm.name()) != _tuple_name(parm)


def _component_value(parm: Any) -> Any:
    data = localize(parm.valueAsData())
    members = _tuple_members(parm)
    if not (_is_tuple_component(parm) and isinstance(data, list) and len(data) == len(members)):
        return data
    names = [localize(item.name()) for item in members]
    return data[names.index(localize(parm.name()))]


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        return success_result({"parm_path": args.parm_path, "value": _component_value(parm)})


def handle_full(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        return success_result({"parm_path": args.parm_path, "value": localize(parm.asData(brief=False))})


def handle_menu(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        items = list(localize(parm.menuItems()))
        labels = list(localize(parm.menuLabels()))
        if not items:
            raise ValueError(f"Parameter does not provide a menu: {args.parm_path}")
        return success_result(
            {
                "parm_path": args.parm_path,
                "current_value": localize(parm.evalAsString()),
                "menu_items": [
                    {"token": token, "label": label}
                    for token, label in zip(items, labels, strict=True)
                ],
            }
        )


def handle_set(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        parm.set(_parse_cli_value(args.value))
        return success_result({"parm_path": args.parm_path, "applied": True})


def _parse_cli_value(raw: str) -> Any:
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


def handle_tuple_set(args: argparse.Namespace) -> dict:
    values = [_parse_cli_value(value) for value in args.values]
    with connect(args.host, args.port) as session:
        parm_tuple = _get_parm_tuple(session, args.parm_path)
        if len(values) != len(parm_tuple):
            raise ValueError(f"Tuple arity mismatch: expected {len(parm_tuple)} values, got {len(values)}")
        parm_tuple.set(values)
        return success_result({"parm_path": args.parm_path, "applied": True})


def _read_text_input(input_value: str) -> str:
    if input_value == "-":
        import sys

        return sys.stdin.read()
    with open(input_value, encoding="utf-8") as handle:
        return handle.read()


def _read_json_input(input_value: str) -> Any:
    import json

    if input_value == "-":
        return load_json_input("-")
    with open(input_value, encoding="utf-8") as handle:
        return json.load(handle)


def handle_text_set(args: argparse.Namespace) -> dict:
    text = _read_text_input(args.input)
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        parm.set(text)
        return success_result({"parm_path": args.parm_path, "applied": True})


def handle_full_set(args: argparse.Namespace) -> dict:
    payload = _read_json_input(args.input)
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        parm.setFromData(payload)
        return success_result({"parm_path": args.parm_path, "applied": True})


SKIPPED_TEMPLATE_TYPES = {"Button", "Folder", "FolderSet", "Label", "Separator"}


def _get_node(session: Any, node_path: str) -> Any:
    node = session.hou.node(node_path)
    if node is None:
        raise ValueError(f"Node not found: {node_path}")
    return node


def _parm_template_type(parm: Any) -> str:
    return localize(parm.parmTemplate().type().name())


def _tuple_type_label(parm: Any) -> str:
    members = _tuple_members(parm)
    base = _parm_template_type(parm)
    return f"{base}{len(members)}" if len(members) > 1 else base


def _parm_flags(parm: Any) -> str:
    members = _tuple_members(parm)
    return "".join(["n" if any(not bool(localize(item.isAtDefault())) for item in members) else ""])


def _parm_display_name(parm: Any) -> str:
    members = _tuple_members(parm)
    return _tuple_name(parm) if len(members) > 1 else localize(parm.name())


def _parm_row_value(parm: Any) -> Any:
    members = _tuple_members(parm)
    data = localize(parm.valueAsData())
    return data if len(members) > 1 else data


def _parm_row(parm: Any) -> list[Any]:
    return [
        _parm_display_name(parm),
        _tuple_type_label(parm),
        _parm_row_value(parm),
        _parm_flags(parm),
    ]


def _iter_discoverable_parms(node: Any) -> list[Any]:
    rows: list[Any] = []
    seen: set[str] = set()
    for parm in node.parms():
        if _parm_template_type(parm) in SKIPPED_TEMPLATE_TYPES:
            continue
        key = localize(parm.path())
        members = _tuple_members(parm)
        if len(members) > 1:
            key = localize(members[0].path())
        if key in seen:
            continue
        seen.add(key)
        rows.append(parm)
    return rows


def _matches_parm(parm: Any, *, name: str | None, parm_type: str | None, non_default: bool) -> bool:
    if non_default and bool(localize(parm.isAtDefault())):
        members = _tuple_members(parm)
        if all(bool(localize(item.isAtDefault())) for item in members):
            return False
    if name:
        needle = name.lower()
        names = [_parm_display_name(parm), *[localize(item.name()) for item in _tuple_members(parm)]]
        lowered = [item.lower() for item in names]
        exact = any(item == needle for item in lowered)
        prefix = any(item.startswith(needle) for item in lowered)
        partial = len(needle) >= 3 and any(needle in item for item in lowered)
        if not (exact or prefix or partial):
            return False
    if parm_type and _tuple_type_label(parm) != parm_type:
        return False
    return True


def handle_node_parms_list(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = _get_node(session, args.node_path)
        rows = [
            _parm_row(parm)
            for parm in _iter_discoverable_parms(node)
            if _matches_parm(parm, name=None, parm_type=None, non_default=args.non_default)
        ][: args.max_parms]
        return success_result(
            {
                "node": args.node_path,
                "count": len(rows),
                "cols": ["p", "t", "v", "f"],
                "rows": rows,
            }
        )


def handle_node_parms_find(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = _get_node(session, args.node_path)
        rows = [
            _parm_row(parm)
            for parm in _iter_discoverable_parms(node)
            if _matches_parm(parm, name=args.name, parm_type=args.parm_type, non_default=args.non_default)
        ][: args.max_parms]
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
            }
        )
