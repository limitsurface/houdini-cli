"""Shared helpers for Houdini digital asset commands."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize


def definition_for_node(node: Any) -> Any:
    definition = node.type().definition()
    if definition is None:
        raise ValueError(f"Node is not an HDA instance: {localize(node.path())}")
    return definition


def save_definition(definition: Any) -> str:
    path = localize(definition.libraryFilePath())
    definition.save(path)
    return path


def type_components(session: Any, type_name: str) -> dict[str, Any]:
    try:
        scope, namespace, name, version = localize(
            session.hou.hda.componentsFromFullNodeTypeName(type_name)
        )
    except Exception:
        scope, namespace, name, version = "", "", type_name, ""
    return {"scope": scope, "namespace": namespace, "name": name, "version": version}


def parm_tree(entries: Any) -> list[dict[str, Any]]:
    result = []
    for template in entries:
        row = {
            "name": localize(template.name()),
            "label": localize(template.label()),
            "type": localize(template.type().name()),
        }
        if hasattr(template, "parmTemplates"):
            row["children"] = parm_tree(template.parmTemplates())
        result.append(row)
    return result


def definition_summary(session: Any, definition: Any) -> dict[str, Any]:
    node_type = definition.nodeType()
    type_name = localize(node_type.name())
    return {
        "type_name": type_name,
        "components": type_components(session, type_name),
        "label": localize(definition.description()),
        "category": localize(node_type.category().name()),
        "library": localize(definition.libraryFilePath()),
        "version": localize(definition.version()),
        "icon": localize(definition.icon()),
        "min_inputs": int(localize(definition.minNumInputs())),
        "max_inputs": int(localize(definition.maxNumInputs())),
        "preferred": bool(localize(definition.isPreferred())),
        "current": bool(localize(definition.isCurrent())),
        "sections": [
            {"name": localize(name), "size": int(localize(section.size()))}
            for name, section in definition.sections().items()
        ],
    }

