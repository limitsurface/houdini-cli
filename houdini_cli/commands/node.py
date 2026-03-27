"""Node commands."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.jsonio import load_json_input
from . import query
from .node_common import get_node, node_summary


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    node_parser = subparsers.add_parser("node", help="Inspect and modify nodes.")
    node_subparsers = node_parser.add_subparsers(dest="node_command", required=True)

    create_parser = node_subparsers.add_parser("create", help="Create a node.")
    create_parser.add_argument("parent_path", help="Parent Houdini node path.")
    create_parser.add_argument("node_type", help="Houdini node type name.")
    create_parser.add_argument("--name", help="Optional node name.")
    create_parser.set_defaults(handler=handle_create)

    delete_parser = node_subparsers.add_parser("delete", help="Delete a node.")
    delete_parser.add_argument("node_path", help="Node path to delete.")
    delete_parser.set_defaults(handler=handle_delete)

    get_parser = node_subparsers.add_parser("get", help="Get a focused summary for a node.")
    get_parser.add_argument("node_path", help="Node path to inspect.")
    get_parser.add_argument(
        "--section",
        choices=("parms", "inputs", "full"),
        help="Return a structured node section instead of the default focused summary.",
    )
    get_parser.set_defaults(handler=handle_get)

    set_parser = node_subparsers.add_parser("set", help="Apply structured node data.")
    set_parser.add_argument("node_path", help="Node path to modify.")
    set_parser.add_argument(
        "--section",
        choices=("parms", "inputs", "full"),
        required=True,
        help="Structured node section to apply.",
    )
    set_parser.add_argument(
        "--json",
        required=True,
        help="JSON payload or '-' to read from stdin.",
    )
    set_parser.set_defaults(handler=handle_set)

    query.register_parser(node_subparsers)


def handle_create(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parent = get_node(session, args.parent_path)
        created = parent.createNode(args.node_type, args.name) if args.name else parent.createNode(args.node_type)
        return success_result(node_summary(created))


def handle_delete(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        summary = {
            "path": localize(node.path()),
            "name": localize(node.name()),
            "type": localize(node.type().name()),
        }
        node.destroy()
        return success_result({"deleted": True, "node": summary})


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        if args.section == "parms":
            return success_result(
                {
                    "node_path": args.node_path,
                    "section": "parms",
                    "value": localize(node.parmsAsData(brief=False)),
                }
            )
        if args.section == "inputs":
            return success_result(
                {
                    "node_path": args.node_path,
                    "section": "inputs",
                    "value": localize(node.inputsAsData()),
                }
            )
        if args.section == "full":
            return success_result(
                {
                    "node_path": args.node_path,
                    "section": "full",
                    "value": localize(
                        node.asData(
                            children=False,
                            editables=False,
                            inputs=True,
                            position=True,
                            flags=True,
                            parms=True,
                            parmtemplates="spare_only",
                        )
                    ),
                }
            )
        return success_result(node_summary(node))


def handle_set(args: argparse.Namespace) -> dict:
    payload = load_json_input(args.json)
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        if args.section == "parms":
            node.setParmsFromData(payload)
        elif args.section == "inputs":
            node.setInputsFromData(payload)
        else:
            node.setFromData(payload)
        return success_result(
            {
                "node_path": args.node_path,
                "section": args.section,
                "applied": True,
            }
        )
