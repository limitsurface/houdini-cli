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

    set_parser = parm_subparsers.add_parser("set", help="Set parameter value or full parameter data.")
    set_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    set_parser.add_argument(
        "--json",
        required=True,
        help="JSON payload or '-' to read from stdin.",
    )
    set_parser.add_argument(
        "--full",
        action="store_true",
        help="Apply full parameter data via Parm.setFromData().",
    )
    set_parser.set_defaults(handler=handle_set)


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


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        return success_result({"parm_path": args.parm_path, "value": localize(parm.valueAsData())})


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
    payload = load_json_input(args.json)
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        if args.full:
            parm.setFromData(payload)
        else:
            if isinstance(payload, (int, float, str, bool)):
                parm.set(payload)
            else:
                parm.setValueFromData(payload)
        return success_result({"parm_path": args.parm_path, "applied": True})


SKIPPED_TEMPLATE_TYPES = {"Button", "Folder", "FolderSet", "Label", "Separator"}


def _get_node(session: Any, node_path: str) -> Any:
    node = session.hou.node(node_path)
    if node is None:
        raise ValueError(f"Node not found: {node_path}")
    return node


def _parm_template_type(parm: Any) -> str:
    return localize(parm.parmTemplate().type().name())


def _parm_flags(parm: Any) -> str:
    return "".join(["n" if not bool(localize(parm.isAtDefault())) else ""])


def _parm_row(parm: Any) -> list[Any]:
    return [
        localize(parm.name()),
        _parm_template_type(parm),
        localize(parm.valueAsData()),
        _parm_flags(parm),
    ]


def _iter_discoverable_parms(node: Any) -> list[Any]:
    return [parm for parm in node.parms() if _parm_template_type(parm) not in SKIPPED_TEMPLATE_TYPES]


def _matches_parm(parm: Any, *, name: str | None, parm_type: str | None, non_default: bool) -> bool:
    if non_default and bool(localize(parm.isAtDefault())):
        return False
    if name and name.lower() not in localize(parm.name()).lower():
        return False
    if parm_type and _parm_template_type(parm) != parm_type:
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
