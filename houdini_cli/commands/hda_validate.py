"""HDA validation commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .hda_common import definition_for_node
from .node_common import get_node


def _node_messages(node: Any) -> dict[str, list[str]]:
    return {
        "errors": [localize(value) for value in node.errors()],
        "warnings": [localize(value) for value in node.warnings()],
        "messages": [localize(value) for value in node.messages()],
    }


def _temporary_name(parent: Any) -> str:
    base = "__hda_validate_tmp"
    name = base
    suffix = 1
    while parent.node(name) is not None:
        name = f"{base}{suffix}"
        suffix += 1
    return name


def validate_asset(
    session: Any,
    node: Any,
    *,
    fresh: bool,
    cook: bool,
    frames: list[float],
) -> dict[str, Any]:
    definition = definition_for_node(node)
    result = {
        "definition_current": bool(localize(definition.isCurrent())),
        "locked": bool(localize(node.isLockedHDA())),
        "matches": bool(localize(node.matchesCurrentDefinition())),
        "library": localize(definition.libraryFilePath()),
    }
    target = node
    temporary = None
    if fresh:
        parent = node.parent()
        temporary = parent.createNode(localize(node.type().name()), _temporary_name(parent))
        for index, source in enumerate(node.inputs()):
            if source is not None:
                temporary.setInput(index, source)
        target = temporary
        result["fresh_instance"] = localize(target.path())
    original_frame = float(localize(session.hou.frame()))
    try:
        frame_results = []
        for frame in frames or ([original_frame] if cook else []):
            session.hou.setFrame(frame)
            target.cook(force=True)
            frame_results.append({"frame": frame, **_node_messages(target)})
        result["frames"] = frame_results
        result["parms"] = len(target.parms())
        result["input_count"] = len([item for item in target.inputs() if item is not None])
        result["output_count"] = len(target.outputs())
        result["compress"] = (
            bool(localize(target.isGenericFlagSet(session.hou.nodeFlag.Compress)))
            if hasattr(target, "isGenericFlagSet")
            else None
        )
    finally:
        session.hou.setFrame(original_frame)
        if temporary is not None:
            temporary.destroy()
    return result


def handle_validate(args: argparse.Namespace) -> dict:
    frames = [float(value) for value in args.frames.split(",")] if args.frames else []
    with connect(args.host, args.port) as session:
        result = validate_asset(
            session,
            get_node(session, args.asset_node),
            fresh=args.fresh_instance,
            cook=args.cook or bool(frames),
            frames=frames,
        )
        warnings = [warning for row in result.get("frames", []) for warning in row["warnings"]]
        if args.strict and warnings:
            raise ValueError(f"Validation warnings: {warnings}")
        return success_result(result)
