"""HDA inspection and library discovery commands."""

from __future__ import annotations

import argparse
import json
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .hda_common import definition_for_node, definition_summary, parm_tree_in_houdini
from .node_common import get_node, node_summary

DEFAULT_DISCOVERY_LIMIT = 50

_DISCOVERY_CODE = r"""
import json as _houdini_cli_json
import hou

def _houdini_cli_type_components(type_name):
    try:
        scope, namespace, name, version = hou.hda.componentsFromFullNodeTypeName(type_name)
    except Exception:
        scope, namespace, name, version = "", "", type_name, ""
    return {"scope": scope, "namespace": namespace, "name": name, "version": version}

def _houdini_cli_definition_row(definition, include_sections=False):
    node_type = definition.nodeType()
    type_name = str(node_type.name())
    row = {
        "type_name": type_name,
        "components": _houdini_cli_type_components(type_name),
        "label": str(definition.description()),
        "category": str(node_type.category().name()),
        "library": str(definition.libraryFilePath()),
        "version": str(definition.version()),
        "icon": str(definition.icon()),
        "min_inputs": int(definition.minNumInputs()),
        "max_inputs": int(definition.maxNumInputs()),
        "preferred": bool(definition.isPreferred()),
        "current": bool(definition.isCurrent()),
    }
    if include_sections:
        row["sections"] = [
            {"name": str(name), "size": int(section.size())}
            for name, section in definition.sections().items()
        ]
    return row

def _houdini_cli_loaded_libraries(library_filter=None):
    paths = [str(path) for path in hou.hda.loadedFiles()]
    if library_filter:
        needle = library_filter.lower()
        paths = [path for path in paths if needle in path.lower()]
    return paths

def _houdini_cli_definition_matches(row, category=None, namespace=None, name=None, type_name=None):
    if category and row["category"].lower() != category.lower():
        return False
    if namespace and row["components"]["namespace"] != namespace:
        return False
    if name and name.lower() not in row["components"]["name"].lower():
        return False
    if type_name and type_name.lower() not in row["type_name"].lower():
        return False
    return True

def _houdini_cli_hda_definition_rows(
    library=None,
    category=None,
    namespace=None,
    name=None,
    type_name=None,
    include_sections=False,
    limit=50,
):
    rows = []
    total_matches = 0
    truncated = False
    paths = [str(library)] if library else _houdini_cli_loaded_libraries()
    for path in paths:
        try:
            definitions = hou.hda.definitionsInFile(path)
        except Exception:
            continue
        for definition in definitions:
            row = _houdini_cli_definition_row(definition, include_sections)
            if not _houdini_cli_definition_matches(row, category, namespace, name, type_name):
                continue
            total_matches += 1
            if limit is not None and len(rows) >= limit:
                truncated = True
                continue
            rows.append(row)
    return {
        "count": len(rows),
        "definitions": rows,
        "total_matches": total_matches,
        "truncated": truncated,
        "limit": limit,
    }

def _houdini_cli_hda_library_rows(
    library_filter=None,
    definition_filter=None,
    limit=50,
):
    rows = []
    total_matches = 0
    truncated = False
    for path in _houdini_cli_loaded_libraries(library_filter):
        try:
            definitions = hou.hda.definitionsInFile(path)
            types = [str(definition.nodeType().name()) for definition in definitions]
        except Exception:
            types = []
        if definition_filter:
            needle = definition_filter.lower()
            if not any(needle in type_name.lower() for type_name in types):
                continue
        total_matches += 1
        if limit is not None and len(rows) >= limit:
            truncated = True
            continue
        rows.append({"path": path, "definition_count": len(types), "types": types})
    return {
        "count": len(rows),
        "libraries": rows,
        "total_matches": total_matches,
        "truncated": truncated,
        "limit": limit,
    }
"""


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


def _limit_from_args(args: argparse.Namespace) -> int | None:
    if getattr(args, "all", False):
        return None
    limit = getattr(args, "max", DEFAULT_DISCOVERY_LIMIT)
    if limit <= 0:
        raise ValueError(f"Limit must be positive: {limit}")
    return limit


def _definition_rows_in_houdini(session: Any, args: argparse.Namespace) -> dict[str, Any]:
    connection = getattr(session, "connection", None)
    if connection is None:
        definitions = (
            list(session.hou.hda.definitionsInFile(args.library))
            if args.library
            else _all_definitions(session)
        )
        rows = []
        total_matches = 0
        limit = _limit_from_args(args)
        for definition in definitions:
            summary = definition_summary(session, definition)
            comp = summary["components"]
            if args.category and summary["category"].lower() != args.category.lower():
                continue
            if args.namespace and comp["namespace"] != args.namespace:
                continue
            if args.name and args.name.lower() not in comp["name"].lower():
                continue
            if args.type_name and args.type_name.lower() not in summary["type_name"].lower():
                continue
            if not args.sections:
                summary.pop("sections", None)
            total_matches += 1
            if limit is not None and len(rows) >= limit:
                continue
            rows.append(summary)
        return {
            "count": len(rows),
            "definitions": rows,
            "total_matches": total_matches,
            "truncated": limit is not None and total_matches > len(rows),
            "limit": limit,
        }

    namespace = connection.namespace
    namespace["_houdini_cli_hda_definition_args"] = {
        "library": args.library,
        "category": args.category,
        "namespace": args.namespace,
        "name": args.name,
        "type_name": args.type_name,
        "include_sections": bool(args.sections),
        "limit": _limit_from_args(args),
    }
    connection.execute(_DISCOVERY_CODE)
    connection.execute(
        "_houdini_cli_hda_definition_json = _houdini_cli_json.dumps("
        "_houdini_cli_hda_definition_rows(**_houdini_cli_hda_definition_args))"
    )
    return json.loads(localize(namespace["_houdini_cli_hda_definition_json"]))


def handle_definitions(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        payload = _definition_rows_in_houdini(session, args)
        meta = {
            "truncated": payload.pop("truncated"),
            "limit": payload.pop("limit"),
            "total_matches": payload.pop("total_matches"),
        }
        if meta["truncated"]:
            meta["next_hint"] = "Refine filters, raise --max, or pass --all for an uncapped scan"
        return success_result(payload, meta=meta)


def _library_rows_in_houdini(session: Any, args: argparse.Namespace) -> dict[str, Any]:
    connection = getattr(session, "connection", None)
    limit = _limit_from_args(args)
    if connection is None:
        rows = []
        total_matches = 0
        for path in localize(session.hou.hda.loadedFiles()):
            if args.library and args.library.lower() not in path.lower():
                continue
            try:
                definitions = session.hou.hda.definitionsInFile(path)
                types = [localize(item.nodeType().name()) for item in definitions]
            except Exception:
                types = []
            if args.definition:
                needle = args.definition.lower()
                if not any(needle in type_name.lower() for type_name in types):
                    continue
            total_matches += 1
            if limit is not None and len(rows) >= limit:
                continue
            rows.append({"path": path, "definition_count": len(types), "types": types})
        return {
            "count": len(rows),
            "libraries": rows,
            "total_matches": total_matches,
            "truncated": limit is not None and total_matches > len(rows),
            "limit": limit,
        }

    namespace = connection.namespace
    namespace["_houdini_cli_hda_library_args"] = {
        "library_filter": args.library,
        "definition_filter": args.definition,
        "limit": limit,
    }
    connection.execute(_DISCOVERY_CODE)
    connection.execute(
        "_houdini_cli_hda_library_json = _houdini_cli_json.dumps("
        "_houdini_cli_hda_library_rows(**_houdini_cli_hda_library_args))"
    )
    return json.loads(localize(namespace["_houdini_cli_hda_library_json"]))


def handle_libraries(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        payload = _library_rows_in_houdini(session, args)
        meta = {
            "truncated": payload.pop("truncated"),
            "limit": payload.pop("limit"),
            "total_matches": payload.pop("total_matches"),
        }
        if meta["truncated"]:
            meta["next_hint"] = "Refine filters, raise --max, or pass --all for an uncapped scan"
        return success_result(payload, meta=meta)
