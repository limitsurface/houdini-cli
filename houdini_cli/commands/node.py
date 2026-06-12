"""Node commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.jsonio import load_json_input
from . import parm
from . import query
from .node_common import get_node, node_summary
from .recipe_common import apply_tool_recipe, find_tool_recipe


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


def handle_create(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parent = get_node(session, args.parent_path)
        recipe = find_tool_recipe(session, args.node_type, str(parent.childTypeCategory().name()))
        if recipe is not None:
            if args.name:
                raise ValueError("--name is not supported when creating a tool recipe")
            return success_result(apply_tool_recipe(session, parent, args.node_type))
        created = parent.createNode(args.node_type, args.name) if args.name else parent.createNode(args.node_type)
        return success_result({**node_summary(created), "kind": "node"})


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Expected boolean value, got: {value}")


def handle_rename(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        old_path = localize(node.path())
        node.setName(args.new_name, unique_name=args.unique)
        return success_result(
            {
                "old_path": old_path,
                "new_path": localize(node.path()),
                "name": localize(node.name()),
            }
        )


def _get_nodes_with_shared_parent(session: Any, node_paths: list[str]) -> tuple[list[Any], Any]:
    nodes = [get_node(session, path) for path in node_paths]
    parents = [node.parent() for node in nodes]
    if not parents or parents[0] is None:
        raise ValueError("Nodes must have a parent network")
    parent_paths = {localize(parent.path()) for parent in parents}
    if len(parent_paths) != 1:
        raise ValueError("Nodes do not share the same parent network")
    return nodes, parents[0]


def _path_map(old_paths: list[str], nodes: Any) -> dict[str, str]:
    returned_nodes = list(nodes)
    if len(returned_nodes) != len(old_paths):
        raise RuntimeError("Houdini returned an unexpected number of nodes")
    return {
        old_path: localize(node.path())
        for old_path, node in zip(old_paths, returned_nodes, strict=True)
    }


def handle_copy(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        nodes, source_parent = _get_nodes_with_shared_parent(session, args.node_paths)
        destination = get_node(session, args.parent)
        old_paths = [localize(node.path()) for node in nodes]
        copied = destination.copyItems(
            tuple(nodes),
            channel_reference_originals=False,
            relative_references=True,
        )
        return success_result(
            {
                "operation": "copy",
                "source_parent": localize(source_parent.path()),
                "destination_parent": localize(destination.path()),
                "path_map": _path_map(old_paths, copied),
            }
        )


def handle_move(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        nodes, source_parent = _get_nodes_with_shared_parent(session, args.node_paths)
        destination = get_node(session, args.parent)
        if localize(source_parent.path()) == localize(destination.path()):
            raise ValueError("Source and destination parent networks are the same")
        old_paths = [localize(node.path()) for node in nodes]
        moved = session.hou.moveNodesTo(tuple(nodes), destination)
        return success_result(
            {
                "operation": "move",
                "source_parent": localize(source_parent.path()),
                "destination_parent": localize(destination.path()),
                "path_map": _path_map(old_paths, moved),
            }
        )


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
        if args.section == "references":
            return success_result(_reference_payload(node, external_only=args.external_only))
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


def _is_within_root(path: str, root_path: str) -> bool:
    return path == root_path or path.startswith(root_path.rstrip("/") + "/")


def _reference_payload(root: Any, *, external_only: bool) -> dict[str, Any]:
    root_path = localize(root.path())
    nodes = [root, *list(root.allSubChildren())]
    parm_rows = []
    input_rows = []

    for node in nodes:
        node_path = localize(node.path())
        for parameter in node.parms():
            try:
                targets = list(parameter.references())
            except Exception:
                continue
            for target in targets:
                target_path = localize(target.path())
                target_node_path = target_path.rsplit("/", 1)[0]
                external = not _is_within_root(target_node_path, root_path)
                if external_only and not external:
                    continue
                parm_rows.append(
                    {
                        "from_parm": localize(parameter.path()),
                        "to_parm": target_path,
                        "external": external,
                    }
                )

        for connection in node.inputConnections():
            source = connection.inputNode()
            if source is None:
                continue
            source_path = localize(source.path())
            external = not _is_within_root(source_path, root_path)
            if external_only and not external:
                continue
            input_rows.append({**_connection_payload(connection), "external": external})

    return {
        "node_path": root_path,
        "section": "references",
        "external_only": external_only,
        "parameter_references": parm_rows,
        "input_references": input_rows,
        "counts": {
            "parameter_references": len(parm_rows),
            "input_references": len(input_rows),
        },
    }


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


def _node_flags(session: Any, node: Any) -> dict[str, bool | None]:
    flags: dict[str, bool | None] = {
        "display": bool(localize(node.isDisplayFlagSet())) if hasattr(node, "isDisplayFlagSet") else None,
        "render": bool(localize(node.isRenderFlagSet())) if hasattr(node, "isRenderFlagSet") else None,
        "bypass": bool(localize(node.isBypassed())) if hasattr(node, "isBypassed") else None,
        "compress": None,
    }
    if hasattr(node, "isGenericFlagSet"):
        flags["compress"] = bool(localize(node.isGenericFlagSet(session.hou.nodeFlag.Compress)))
    return flags


def handle_flags_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        return success_result({"node_path": localize(node.path()), "flags": _node_flags(session, node)})


def handle_flags_set(args: argparse.Namespace) -> dict:
    requested = {
        "display": args.display,
        "render": args.render,
        "bypass": args.bypass,
        "compress": args.compress,
    }
    changes = {name: value for name, value in requested.items() if value is not None}
    if not changes:
        raise ValueError("At least one flag option is required")

    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        if args.display is not None:
            node.setDisplayFlag(args.display)
        if args.render is not None:
            node.setRenderFlag(args.render)
        if args.bypass is not None:
            node.bypass(args.bypass)
        if args.compress is not None:
            node.setGenericFlag(session.hou.nodeFlag.Compress, args.compress)
        return success_result(
            {
                "node_path": localize(node.path()),
                "applied": changes,
                "flags": _node_flags(session, node),
            }
        )
