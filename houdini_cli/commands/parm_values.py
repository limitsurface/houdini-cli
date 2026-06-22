"""Parameter value commands."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.input import read_json_input, read_text_input
from .parm_common import component_value, get_parm, get_parm_tuple, parse_cli_value


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = get_parm(session, args.parm_path)
        return success_result({"parm_path": args.parm_path, "value": component_value(parm)})


def handle_full(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = get_parm(session, args.parm_path)
        return success_result({"parm_path": args.parm_path, "value": localize(parm.asData(brief=False))})


def handle_menu(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = get_parm(session, args.parm_path)
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
        parm = get_parm(session, args.parm_path)
        parm.set(parse_cli_value(args.value))
        return success_result({"parm_path": args.parm_path, "applied": True})


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


def handle_tuple_set(args: argparse.Namespace) -> dict:
    values = [parse_cli_value(value) for value in args.values]
    with connect(args.host, args.port) as session:
        parm_tuple = get_parm_tuple(session, args.parm_path)
        if len(values) != len(parm_tuple):
            raise ValueError(f"Tuple arity mismatch: expected {len(parm_tuple)} values, got {len(values)}")
        parm_tuple.set(values)
        return success_result({"parm_path": args.parm_path, "applied": True})


def handle_text_set(args: argparse.Namespace) -> dict:
    text = read_text_input(args.input)
    with connect(args.host, args.port) as session:
        parm = get_parm(session, args.parm_path)
        parm.set(text)
        return success_result({"parm_path": args.parm_path, "applied": True})


def handle_full_set(args: argparse.Namespace) -> dict:
    payload = read_json_input(args.input)
    with connect(args.host, args.port) as session:
        parm = get_parm(session, args.parm_path)
        parm.setFromData(payload)
        return success_result({"parm_path": args.parm_path, "applied": True})
