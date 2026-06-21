"""Shared Houdini recipe discovery and application helpers."""

from __future__ import annotations

import json
from typing import Any

from ..transport.rpyc import localize

TOOL_RECIPE_CATEGORIES = {"tool_recipe", "tab_tool_recipe"}
RECIPE_CATEGORY_ALIASES = {
    "tool": TOOL_RECIPE_CATEGORIES,
    "decoration": {"decoration_recipe"},
    "node-preset": {"node_preset_recipe"},
    "parm-preset": {"parm_preset_recipe"},
}

_RECIPE_DISCOVERY_CODE = r"""
import json as _houdini_cli_json
import hou

_HOUDINI_CLI_RECIPE_CATEGORY_ALIASES = {
    "tool": {"tool_recipe", "tab_tool_recipe"},
    "decoration": {"decoration_recipe"},
    "node-preset": {"node_preset_recipe"},
    "parm-preset": {"parm_preset_recipe"},
}
_HOUDINI_CLI_TOOL_RECIPE_CATEGORIES = {"tool_recipe", "tab_tool_recipe"}

def _houdini_cli_recipe_payload(node_type):
    definition = node_type.definition()
    if definition is None:
        return None, None
    section = definition.sections().get("data.recipe.json")
    if section is None:
        return definition, None
    try:
        return definition, _houdini_cli_json.loads(section.contents())
    except (TypeError, ValueError):
        return definition, None

def _houdini_cli_recipe_alias(recipe_category):
    for alias, values in _HOUDINI_CLI_RECIPE_CATEGORY_ALIASES.items():
        if recipe_category in values:
            return alias
    return recipe_category

def _houdini_cli_recipe_items(category=None, visible_only=False):
    accepted = _HOUDINI_CLI_RECIPE_CATEGORY_ALIASES.get(category) if category else None
    items = []
    for key, node_type in hou.dataNodeTypeCategory().nodeTypes().items():
        definition, payload = _houdini_cli_recipe_payload(node_type)
        if payload is None:
            continue
        properties = payload.get("properties", {})
        recipe_category = str(properties.get("recipe_category", ""))
        if accepted is not None and recipe_category not in accepted:
            continue
        visible = bool(properties.get("visible", True))
        if visible_only and not visible:
            continue
        tool = payload.get("tool", {})
        items.append({
            "key": str(key),
            "label": str(node_type.description()),
            "category": _houdini_cli_recipe_alias(recipe_category),
            "recipe_category": recipe_category,
            "visible": visible,
            "library": str(definition.libraryFilePath()) if definition else None,
            "network_categories": [str(value) for value in tool.get("network_categories", [])],
            "submenus": [str(value) for value in tool.get("tab_submenus", [])],
        })
    items.sort(key=lambda item: (item["label"].lower(), item["key"].lower()))
    return items

def _houdini_cli_tool_recipe_items(category_name):
    items = []
    for key, node_type in hou.dataNodeTypeCategory().nodeTypes().items():
        definition, payload = _houdini_cli_recipe_payload(node_type)
        if payload is None:
            continue
        properties = payload.get("properties", {})
        tool = payload.get("tool", {})
        if properties.get("recipe_category") not in _HOUDINI_CLI_TOOL_RECIPE_CATEGORIES:
            continue
        if not properties.get("visible", True):
            continue
        network_categories = tool.get("network_categories", [])
        property_category = properties.get("nodetype_category")
        if category_name not in network_categories and category_name != property_category:
            continue
        label = str(node_type.description())
        items.append({
            "key": str(key),
            "description": label + " (recipe)",
            "label": label,
            "kind": "recipe",
            "icon": str(tool.get("icon") or node_type.icon()),
            "submenus": [str(value) for value in tool.get("tab_submenus", [])],
            "recipe_category": str(properties["recipe_category"]),
        })
    items.sort(key=lambda item: (item["description"].lower(), item["key"].lower()))
    return items

def _houdini_cli_get_recipe_item(recipe_key):
    items = _houdini_cli_recipe_items()
    item = next((row for row in items if row["key"] == recipe_key), None)
    if item is None:
        raise ValueError("Recipe not found: " + recipe_key)
    node_type = hou.dataNodeTypeCategory().nodeTypes()[recipe_key]
    _definition, payload = _houdini_cli_recipe_payload(node_type)
    return dict(item, payload=payload or {})
"""


def _remote_json(session: Any, expression: str, values: dict[str, Any] | None = None) -> Any | None:
    connection = getattr(session, "connection", None)
    if connection is None:
        return None
    namespace = connection.namespace
    for key, value in (values or {}).items():
        namespace[key] = value
    connection.execute(_RECIPE_DISCOVERY_CODE)
    connection.execute(f"_houdini_cli_recipe_result_json = _houdini_cli_json.dumps({expression})")
    return json.loads(localize(namespace["_houdini_cli_recipe_result_json"]))


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
    remote = _remote_json(
        session,
        "_houdini_cli_tool_recipe_items(_houdini_cli_recipe_category_name)",
        {"_houdini_cli_recipe_category_name": category_name},
    )
    if remote is not None:
        return remote

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


def recipe_items(session: Any, *, category: str | None = None, visible_only: bool = False) -> list[dict[str, Any]]:
    remote = _remote_json(
        session,
        "_houdini_cli_recipe_items(_houdini_cli_recipe_category, _houdini_cli_recipe_visible_only)",
        {
            "_houdini_cli_recipe_category": category,
            "_houdini_cli_recipe_visible_only": bool(visible_only),
        },
    )
    if remote is not None:
        return remote

    accepted = RECIPE_CATEGORY_ALIASES.get(category) if category else None
    items = []
    for key, node_type in session.hou.dataNodeTypeCategory().nodeTypes().items():
        payload = _recipe_payload(node_type)
        if payload is None:
            continue
        definition = node_type.definition()
        properties = payload.get("properties", {})
        recipe_category = str(properties.get("recipe_category", ""))
        if accepted is not None and recipe_category not in accepted:
            continue
        visible = bool(properties.get("visible", True))
        if visible_only and not visible:
            continue
        tool = payload.get("tool", {})
        items.append(
            {
                "key": str(key),
                "label": str(node_type.description()),
                "category": next(
                    (alias for alias, values in RECIPE_CATEGORY_ALIASES.items() if recipe_category in values),
                    recipe_category,
                ),
                "recipe_category": recipe_category,
                "visible": visible,
                "library": localize(definition.libraryFilePath()) if definition else None,
                "network_categories": [str(value) for value in tool.get("network_categories", [])],
                "submenus": [str(value) for value in tool.get("tab_submenus", [])],
            }
        )
    items.sort(key=lambda item: (item["label"].lower(), item["key"].lower()))
    return items


def get_recipe_item(session: Any, recipe_key: str) -> dict[str, Any]:
    remote = _remote_json(
        session,
        "_houdini_cli_get_recipe_item(_houdini_cli_recipe_key)",
        {"_houdini_cli_recipe_key": recipe_key},
    )
    if remote is not None:
        return remote

    item = next((row for row in recipe_items(session) if row["key"] == recipe_key), None)
    if item is None:
        raise ValueError(f"Recipe not found: {recipe_key}")
    node_type = session.hou.dataNodeTypeCategory().nodeTypes()[recipe_key]
    payload = _recipe_payload(node_type) or {}
    return {**item, "payload": payload}


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
