"""Node data, messages, connections, and flags."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..remote.node_parms import NODE_PARMS_REMOTE
from ..transport.rpyc import connect, localize
from ..util.jsonio import load_json_input
from .node_common import get_node, node_summary
from .node_parm_values import parm_projection_item
from .node_references import reference_payload_in_houdini as _reference_payload_in_houdini


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Expected boolean value, got: {value}")


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        requested_parms = getattr(args, "parm_names", None) or []
        if requested_parms and args.section != "parms":
            raise ValueError("--parm requires --section parms")
        if args.section == "parms":
            structured_value = getattr(args, "structured_value", "full")
            max_items = getattr(args, "max_items", 10)
            if max_items < 1:
                raise ValueError("max items must be at least one")
            if structured_value == "summary" and not requested_parms:
                raise ValueError("--structured-value summary requires at least one --parm")
            if requested_parms:
                connection = getattr(session, "connection", None)
                if connection is not None:
                    projected = localize(
                        NODE_PARMS_REMOTE.evaluate(
                            connection,
                            "project",
                            args.node_path,
                            requested_parms,
                            structured_value,
                            int(max_items),
                        )
                    )
                    items = projected["items"]
                    missing = projected["missing"]
                else:
                    items = []
                    missing = []
                    for name in requested_parms:
                        parm = node.parm(name)
                        if parm is None:
                            parm_tuple = node.parmTuple(name)
                            if parm_tuple is not None and len(parm_tuple):
                                parm = parm_tuple[0]
                        if parm is None:
                            missing.append(name)
                            continue
                        items.append(
                            parm_projection_item(
                                parm,
                                mode=structured_value,
                                max_items=max_items,
                                display_name=name,
                            )
                        )
                return success_result(
                    {
                        "node_path": args.node_path,
                        "section": "parms",
                        "items": items,
                    },
                    meta={
                        "missing": missing,
                        "requested": len(requested_parms),
                        "returned": len(items),
                        "max_items": max_items,
                        "structured_value": structured_value,
                    },
                )
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
            return success_result(
                _reference_payload_in_houdini(
                    session,
                    args.node_path,
                    fallback_root=node,
                    external_only=args.external_only,
                )
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
            if getattr(args, "cook", False) and hasattr(node, "cook"):
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
