"""Shared Houdini recipe discovery and application helpers."""

from __future__ import annotations

import json
from typing import Any

from ..transport.rpyc import localize

TOOL_RECIPE_CATEGORIES = {"tool_recipe", "tab_tool_recipe"}


def _recipe_payload(node_type: Any) -> dict[str, Any] | None:
    definition = node_type.definition()
    if definition is None:
        return None
    section = definition.sections().get("data.recipe.json")
    if section is None:
        return None
    try:
        return json.loads(localize(section.contents()))
    except (TypeError, ValueError):
        return None


def tool_recipe_items(session: Any, category_name: str) -> list[dict[str, Any]]:
    items = []
    for key, node_type in session.hou.dataNodeTypeCategory().nodeTypes().items():
        payload = _recipe_payload(node_type)
        if payload is None:
            continue
        properties = payload.get("properties", {})
        tool = payload.get("tool", {})
        if properties.get("recipe_category") not in TOOL_RECIPE_CATEGORIES:
            continue
        if not properties.get("visible", True):
            continue
        network_categories = tool.get("network_categories", [])
        property_category = properties.get("nodetype_category")
        if category_name not in network_categories and category_name != property_category:
            continue
        items.append(
            {
                "key": str(key),
                "description": f"{node_type.description()} (recipe)",
                "label": str(node_type.description()),
                "kind": "recipe",
                "icon": str(tool.get("icon") or node_type.icon()),
                "submenus": [str(value) for value in tool.get("tab_submenus", [])],
                "recipe_category": str(properties["recipe_category"]),
            }
        )
    items.sort(key=lambda item: (item["description"].lower(), item["key"].lower()))
    return items


def find_tool_recipe(session: Any, recipe_key: str, category_name: str) -> dict[str, Any] | None:
    return next(
        (item for item in tool_recipe_items(session, category_name) if item["key"] == recipe_key),
        None,
    )


def apply_tool_recipe(session: Any, parent: Any, recipe_key: str) -> dict[str, Any]:
    connection = getattr(session, "connection", None)
    if connection is not None:
        namespace = connection.namespace
        namespace["_houdini_cli_recipe_key"] = recipe_key
        namespace["_houdini_cli_recipe_parent_path"] = localize(parent.path())
        connection.execute(
            """
import hou as _houdini_cli_hou
import json as _houdini_cli_json

_houdini_cli_parent = _houdini_cli_hou.node(_houdini_cli_recipe_parent_path)
_houdini_cli_result = _houdini_cli_hou.data.applyToolRecipe(
    _houdini_cli_recipe_key,
    parent=_houdini_cli_parent,
    tool_inputs=(),
    tool_outputs=(),
    prompt=False,
    click_to_place=False,
    avoid_overlap=True,
    frame=False,
)
_houdini_cli_recipe_result_json = _houdini_cli_json.dumps({
    "kind": "recipe",
    "recipe": _houdini_cli_recipe_key,
    "parent": _houdini_cli_parent.path(),
    "items": {
        str(key): item.path()
        for key, item in _houdini_cli_result.get("items", {}).items()
    },
    "current_node": (
        _houdini_cli_result["current_node"].path()
        if _houdini_cli_result.get("current_node") is not None
        else None
    ),
    "selected_nodes": [
        item.path()
        for item in _houdini_cli_result.get("selected_nodes", ())
    ],
})
"""
        )
        return json.loads(localize(namespace["_houdini_cli_recipe_result_json"]))

    result = session.hou.data.applyToolRecipe(
        recipe_key,
        parent=parent,
        tool_inputs=(),
        tool_outputs=(),
        prompt=False,
        click_to_place=False,
        avoid_overlap=True,
        frame=False,
    )
    return localize({
        "kind": "recipe",
        "recipe": recipe_key,
        "parent": localize(parent.path()),
        "items": {str(key): localize(item.path()) for key, item in result.get("items", {}).items()},
        "current_node": (
            localize(result["current_node"].path())
            if result.get("current_node") is not None
            else None
        ),
        "selected_nodes": [
            localize(item.path())
            for item in result.get("selected_nodes", ())
        ],
    })
