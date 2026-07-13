"""Node command parser and dispatch."""

from __future__ import annotations

import argparse

from . import parm
from . import query
from .node_inspect import (
    _parse_bool,
    handle_connections,
    handle_errors,
    handle_flags_get,
    handle_flags_set,
    handle_get,
    handle_set,
)
from .node_lifecycle import handle_copy, handle_create, handle_delete, handle_move, handle_rename
from .node_nav import handle_nav


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    node_parser = subparsers.add_parser("node", help="Inspect and modify nodes.")
    node_subparsers = node_parser.add_subparsers(dest="node_command", required=True)

    create_parser = node_subparsers.add_parser("create", help="Create a node.")
    create_parser.add_argument("parent_path", help="Parent Houdini node path.")
    create_parser.add_argument("node_type", help="Houdini node type name.")
    create_parser.add_argument("--name", help="Optional node name.")
    create_parser.set_defaults(handler=handle_create)

    rename_parser = node_subparsers.add_parser("rename", help="Rename a node.")
    rename_parser.add_argument("node_path", help="Node path to rename.")
    rename_parser.add_argument("new_name", help="New node name.")
    rename_parser.add_argument(
        "--unique",
        action="store_true",
        help="Allow Houdini to choose a unique suffix when the name is occupied.",
    )
    rename_parser.set_defaults(handler=handle_rename)

    copy_parser = node_subparsers.add_parser("copy", help="Copy nodes to another network.")
    copy_parser.add_argument("node_paths", nargs="+", help="Node paths to copy.")
    copy_parser.add_argument("--parent", required=True, help="Destination parent network.")
    copy_parser.set_defaults(handler=handle_copy)

    move_parser = node_subparsers.add_parser("move", help="Move nodes to another network.")
    move_parser.add_argument("node_paths", nargs="+", help="Node paths to move.")
    move_parser.add_argument("--parent", required=True, help="Destination parent network.")
    move_parser.set_defaults(handler=handle_move)

    delete_parser = node_subparsers.add_parser("delete", help="Delete a node.")
    delete_parser.add_argument("node_path", help="Node path to delete.")
    delete_parser.set_defaults(handler=handle_delete)

    nav_parser = node_subparsers.add_parser("nav", help="Navigate a Network Editor to one or more nodes.")
    nav_parser.add_argument("node_paths", nargs="+", help="One or more node paths in the same parent network.")
    nav_parser.add_argument(
        "--no-frame",
        action="store_true",
        help="Do not frame the target nodes in the Network Editor.",
    )
    nav_parser.add_argument(
        "--no-select",
        action="store_true",
        help="Do not leave the target nodes selected.",
    )
    nav_parser.add_argument(
        "--no-current",
        action="store_true",
        help="Do not set the last node as the current node.",
    )
    nav_parser.set_defaults(handler=handle_nav)

    get_parser = node_subparsers.add_parser("get", help="Get a focused summary for a node.")
    get_parser.add_argument("node_path", help="Node path to inspect.")
    get_parser.add_argument(
        "--section",
        choices=("parms", "inputs", "references", "full"),
        help="Return a structured node section instead of the default focused summary.",
    )
    get_parser.add_argument(
        "--external-only",
        action="store_true",
        help="For references, return only dependencies outside the inspected root.",
    )
    get_parser.add_argument(
        "--parm",
        dest="parm_names",
        action="append",
        help="Project one exact parameter or tuple name; repeat to preserve a requested order.",
    )
    get_parser.add_argument(
        "--max-items",
        type=int,
        default=10,
        help="Maximum nested summary items per projected parameter (default: 10).",
    )
    get_parser.add_argument(
        "--structured-value",
        choices=("full", "summary"),
        default="full",
        help="Return full or bounded-summary values for --parm projections.",
    )
    get_parser.set_defaults(handler=handle_get)

    errors_parser = node_subparsers.add_parser("errors", help="Get errors, warnings, and messages for nodes.")
    errors_parser.add_argument("node_paths", nargs="+", help="One or more node paths to inspect.")
    errors_parser.add_argument(
        "--cook",
        action="store_true",
        help="Cook each node before reading messages. By default existing messages are read without cooking.",
    )
    errors_parser.set_defaults(handler=handle_errors)

    connections_parser = node_subparsers.add_parser(
        "connections",
        help="Get stable, explicit connection data for a node.",
    )
    connections_parser.add_argument("node_path", help="Node path to inspect.")
    connections_parser.set_defaults(handler=handle_connections)

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

    flags_parser = node_subparsers.add_parser("flags", help="Read or set focused node flags.")
    flags_subparsers = flags_parser.add_subparsers(dest="node_flags_command", required=True)

    flags_get_parser = flags_subparsers.add_parser("get", help="Read focused node flags.")
    flags_get_parser.add_argument("node_path", help="Node path to inspect.")
    flags_get_parser.set_defaults(handler=handle_flags_get)

    flags_set_parser = flags_subparsers.add_parser("set", help="Set focused node flags.")
    flags_set_parser.add_argument("node_path", help="Node path to modify.")
    flags_set_parser.add_argument("--display", type=_parse_bool)
    flags_set_parser.add_argument("--render", type=_parse_bool)
    flags_set_parser.add_argument("--bypass", type=_parse_bool)
    flags_set_parser.add_argument("--compress", type=_parse_bool)
    flags_set_parser.set_defaults(handler=handle_flags_set)

    parm.register_node_parms_parser(node_subparsers)
    query.register_parser(node_subparsers)
