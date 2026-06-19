"""HDA inspection and library discovery commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .hda_common import definition_for_node, definition_summary, parm_tree_in_houdini
from .node_common import get_node, node_summary


def handle_inspect(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.asset_node)
        definition = definition_for_node(node)
        data = {
            "node": node_summary(node),
            "definition": definition_summary(session, definition),
            "locked": bool(localize(node.isLockedHDA())),
            "matches": bool(localize(node.matchesCurrentDefinition())),
        }
        if args.parms:
            data["parms"] = parm_tree_in_houdini(session, args.asset_node)
        if args.sections:
            data["section_names"] = [localize(name) for name in definition.sections().keys()]
        if args.tools:
            data["tools"] = [localize(name) for name in definition.tools().keys()]
        if hasattr(node, "isGenericFlagSet"):
            data["compress"] = bool(
                localize(node.isGenericFlagSet(session.hou.nodeFlag.Compress))
            )
        return success_result(data)


def _all_definitions(session: Any) -> list[Any]:
    definitions = []
    for library in localize(session.hou.hda.loadedFiles()):
        try:
            definitions.extend(session.hou.hda.definitionsInFile(library))
        except Exception:
            continue
    return definitions


def handle_definitions(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        definitions = (
            list(session.hou.hda.definitionsInFile(args.library))
            if args.library
            else _all_definitions(session)
        )
        rows = []
        for definition in definitions:
            summary = definition_summary(session, definition)
            comp = summary["components"]
            if args.category and summary["category"].lower() != args.category.lower():
                continue
            if args.namespace and comp["namespace"] != args.namespace:
                continue
            if args.name and args.name.lower() not in comp["name"].lower():
                continue
            rows.append(summary)
        return success_result({"count": len(rows), "definitions": rows})


def handle_libraries(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        rows = []
        for path in localize(session.hou.hda.loadedFiles()):
            try:
                definitions = session.hou.hda.definitionsInFile(path)
                types = [localize(item.nodeType().name()) for item in definitions]
            except Exception:
                types = []
            rows.append({"path": path, "definition_count": len(types), "types": types})
        return success_result({"count": len(rows), "libraries": rows})
