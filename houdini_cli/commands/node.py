"""Node commands."""

from __future__ import annotations

import argparse
from typing import Any

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
        choices=("parms", "inputs", "full"),
        help="Return a structured node section instead of the default focused summary.",
    )
    get_parser.set_defaults(handler=handle_get)

    errors_parser = node_subparsers.add_parser("errors", help="Get errors, warnings, and messages for nodes.")
    errors_parser.add_argument("node_paths", nargs="+", help="One or more node paths to inspect.")
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


def _get_parent_path(node) -> str:
    parent = node.parent()
    if parent is None:
        raise ValueError(f"Node has no parent network: {localize(node.path())}")
    return localize(parent.path())


def _get_network_editor(session):
    if not session.hou.isUIAvailable():
        raise ValueError("Houdini UI is not available")

    for pane_tab in session.hou.ui.paneTabs():
        if all(hasattr(pane_tab, name) for name in ("setPwd", "setCurrentNode", "frameSelection")):
            return pane_tab
    raise ValueError("No Network Editor pane is available")


def handle_nav(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        nodes = [get_node(session, node_path) for node_path in args.node_paths]
        parent_paths = {_get_parent_path(node) for node in nodes}
        if len(parent_paths) != 1:
            raise ValueError("Nodes do not share the same parent network")

        network_editor = _get_network_editor(session)
        network = get_node(session, parent_paths.pop())
        network_editor.setPwd(network)

        selected = not args.no_select
        frame = not args.no_frame
        set_current = not args.no_current

        if selected or frame:
            for index, target_node in enumerate(nodes):
                target_node.setSelected(True, clear_all_selected=index == 0)
        else:
            network_editor.clearAllSelected()

        if set_current:
            network_editor.setCurrentNode(nodes[-1])

        framed = False
        if frame:
            network_editor.frameSelection()
            framed = True

        if not selected:
            network_editor.clearAllSelected()

        return success_result(
            {
                "network": localize(network.path()),
                "nodes": [localize(node.path()) for node in nodes],
                "selected": selected,
                "current": localize(nodes[-1].path()) if set_current else None,
                "framed": framed,
            }
        )


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


def _node_messages(node: Any) -> dict[str, list[str]]:
    return {
        "errors": [localize(item) for item in node.errors()],
        "warnings": [localize(item) for item in node.warnings()],
        "messages": [localize(item) for item in node.messages()],
    }


def handle_errors(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        items = []
        for node_path in args.node_paths:
            node = get_node(session, node_path)
            if hasattr(node, "cook"):
                try:
                    node.cook(force=True)
                except Exception:
                    pass
            items.append({"node_path": localize(node.path()), **_node_messages(node)})
        return success_result({"count": len(items), "items": items})


def _connection_payload(connection: Any) -> dict[str, Any]:
    source = connection.inputNode()
    dest = connection.outputNode()
    return {
        "from_path": localize(source.path()) if source is not None else None,
        "from_output_index": int(localize(connection.outputIndex())),
        "from_output_name": localize(connection.inputName()),
        "from_output_label": localize(connection.inputLabel()),
        "to_path": localize(dest.path()) if dest is not None else None,
        "to_input_index": int(localize(connection.inputIndex())),
        "to_input_name": localize(connection.outputName()),
        "to_input_label": localize(connection.outputLabel()),
    }


def handle_connections(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        return success_result(
            {
                "node_path": localize(node.path()),
                "inputs": [_connection_payload(connection) for connection in node.inputConnections()],
                "outputs": [_connection_payload(connection) for connection in node.outputConnections()],
            }
        )


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
