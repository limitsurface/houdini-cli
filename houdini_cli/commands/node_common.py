"""Shared node lookup and summary helpers."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize


def get_node(session: Any, node_path: str) -> Any:
    node = session.hou.node(node_path)
    if node is None:
        raise ValueError(f"Node not found: {node_path}")
    return node


def node_summary(node: Any) -> dict:
    summary = {
        "path": localize(node.path()),
        "name": localize(node.name()),
        "type": localize(node.type().name()),
        "category": localize(node.type().category().name()),
        "child_count": len(node.children()),
        "input_count": len([inp for inp in node.inputs() if inp is not None]),
        "output_count": len(node.outputs()),
    }

    if hasattr(node, "isDisplayFlagSet"):
        summary["display"] = bool(localize(node.isDisplayFlagSet()))
    if hasattr(node, "isRenderFlagSet"):
        summary["render"] = bool(localize(node.isRenderFlagSet()))
    if hasattr(node, "isBypassed"):
        summary["bypass"] = bool(localize(node.isBypassed()))

    return summary
