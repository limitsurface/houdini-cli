"""HDA validation commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .hda_common import definition_for_node
from .node_common import get_node, node_connector_count
from .parm_refs import external_references_in_houdini


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


def _node_type_name(node: Any) -> str:
    return str(localize(node.type().name()))


def _cop_output_audit(node: Any) -> dict[str, Any] | None:
    if str(localize(node.type().category().name())) != "Cop":
        return None

    output_nodes = [child for child in node.children() if _node_type_name(child) == "output"]
    canonical = next((child for child in output_nodes if localize(child.name()) == "outputs"), None)
    extras = [child for child in output_nodes if child is not canonical]
    warnings: list[str] = []
    if canonical is None:
        warnings.append("Copernicus HDA is missing the canonical Output COP named 'outputs'.")
    if extras:
        warnings.append(
            "Copernicus HDA contains additional Output COPs that are not exported: "
            + ", ".join(str(localize(child.path())) for child in extras)
            + ". Route every published result into the canonical 'outputs' node."
        )
    return {
        "canonical": localize(canonical.path()) if canonical is not None else None,
        "count": len(output_nodes),
        "items": [localize(child.path()) for child in output_nodes],
        "extra_count": len(extras),
        "extras": [localize(child.path()) for child in extras],
        "warnings": warnings,
        "ok": not warnings,
    }


def _template_conditionals(group: Any, name: str) -> dict[str, str]:
    template = group.find(name)
    if template is None or not hasattr(template, "conditionals"):
        return {}
    return {
        str(localize(key.name())): str(localize(value))
        for key, value in template.conditionals().items()
    }


def _conditional_ui_audit(node: Any, definition: Any) -> dict[str, Any]:
    definition_group = definition.parmTemplateGroup()
    instance_group = node.parmTemplateGroup()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for parm in node.parms():
        try:
            name = str(localize(parm.tuple().name()))
        except Exception:
            name = str(localize(parm.name()))
        if name in seen:
            continue
        seen.add(name)
        definition_rules = _template_conditionals(definition_group, name)
        instance_rules = _template_conditionals(instance_group, name)
        if not definition_rules and not instance_rules:
            continue
        rows.append(
            {
                "parm": name,
                "definition": definition_rules,
                "instance": instance_rules,
                "matches": definition_rules == instance_rules,
            }
        )
    mismatches = [row for row in rows if not row["matches"]]
    return {
        "count": len(rows),
        "items": rows,
        "mismatch_count": len(mismatches),
        "ok": not mismatches,
    }


def validate_asset(
    session: Any,
    node: Any,
    *,
    fresh: bool,
    cook: bool,
    frames: list[float],
    external_references: bool = False,
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
        validation_warnings: list[str] = []
        frame_results = []
        for frame in frames or ([original_frame] if cook else []):
            session.hou.setFrame(frame)
            target.cook(force=True)
            frame_results.append({"frame": frame, **_node_messages(target)})
        result["frames"] = frame_results
        result["parms"] = len(target.parms())
        result["input_count"] = node_connector_count(target, output=False)
        result["output_count"] = node_connector_count(target, output=True)
        cop_outputs = _cop_output_audit(target)
        if cop_outputs is not None:
            result["cop_outputs"] = cop_outputs
            validation_warnings.extend(cop_outputs["warnings"])
        conditional_ui = _conditional_ui_audit(target, definition)
        result["conditional_ui"] = conditional_ui
        if not conditional_ui["ok"]:
            validation_warnings.append(
                "Published HDA parameter conditionals differ between the definition and instance."
            )
        result["warnings"] = validation_warnings
        result["ok"] = not validation_warnings
        result["compress"] = (
            bool(localize(target.isGenericFlagSet(session.hou.nodeFlag.Compress)))
            if hasattr(target, "isGenericFlagSet")
            else None
        )
        if external_references:
            result["external_references"] = external_references_in_houdini(session, target)
            result["ok"] = result["ok"] and result["external_references"]["count"] == 0
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
            external_references=args.external_references or args.strict,
        )
        warnings = [
            *result.get("warnings", []),
            *[warning for row in result.get("frames", []) for warning in row["warnings"]],
        ]
        if args.strict and warnings:
            raise ValueError(f"Validation warnings: {warnings}")
        external_count = result.get("external_references", {}).get("count", 0)
        if args.strict and external_count:
            raise ValueError(f"External HDA parameter references: {external_count}")
        return success_result(result)
