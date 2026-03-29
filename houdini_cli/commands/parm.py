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

    get_parser = parm_subparsers.add_parser("get", help="Get parameter value or full parameter data.")
    get_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    get_parser.add_argument(
        "--full",
        action="store_true",
        help="Return full parameter data via Parm.asData().",
    )
    get_parser.set_defaults(handler=handle_get)

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


def _get_parm(session: Any, parm_path: str) -> Any:
    parm = session.hou.parm(parm_path)
    if parm is None:
        raise ValueError(f"Parameter not found: {parm_path}")
    return parm


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        data = parm.asData(brief=False) if args.full else parm.valueAsData()
        data = localize(data)
        return success_result({"parm_path": args.parm_path, "value": data})


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
