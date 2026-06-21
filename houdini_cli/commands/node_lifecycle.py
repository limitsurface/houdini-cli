"""Node creation, naming, copying, moving, and deletion."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .node_common import get_node, node_summary
from .recipe_common import apply_tool_recipe, find_tool_recipe


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
