"""Node type discovery commands."""

from __future__ import annotations

import argparse
import json
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .recipe_common import tool_recipe_items

DEFAULT_LIMIT = 50
VALID_CATEGORIES = ("obj", "sop", "cop", "vop", "rop", "lop", "dop", "shop")

_BULK_DISCOVERY_CODE = """
import json as _houdini_cli_json
import hou

_houdini_cli_category = {
    "obj": hou.objNodeTypeCategory,
    "sop": hou.sopNodeTypeCategory,
    "cop": hou.copNodeTypeCategory,
    "vop": hou.vopNodeTypeCategory,
    "rop": hou.ropNodeTypeCategory,
    "lop": hou.lopNodeTypeCategory,
    "dop": hou.dopNodeTypeCategory,
    "shop": hou.shopNodeTypeCategory,
}[_houdini_cli_category_key]()
_houdini_cli_items = [
    {
        "key": str(_houdini_cli_key),
        "description": str(_houdini_cli_type.description()),
        "kind": "node",
    }
    for _houdini_cli_key, _houdini_cli_type
    in _houdini_cli_category.nodeTypes().items()
]
_houdini_cli_category_name = str(_houdini_cli_category.name())
for _houdini_cli_key, _houdini_cli_type in hou.dataNodeTypeCategory().nodeTypes().items():
    _houdini_cli_definition = _houdini_cli_type.definition()
    if _houdini_cli_definition is None:
        continue
    _houdini_cli_section = _houdini_cli_definition.sections().get("data.recipe.json")
    if _houdini_cli_section is None:
        continue
    try:
        _houdini_cli_payload = _houdini_cli_json.loads(_houdini_cli_section.contents())
    except (TypeError, ValueError):
        continue
    _houdini_cli_properties = _houdini_cli_payload.get("properties", {})
    _houdini_cli_tool = _houdini_cli_payload.get("tool", {})
    if _houdini_cli_properties.get("recipe_category") not in {"tool_recipe", "tab_tool_recipe"}:
        continue
    if not _houdini_cli_properties.get("visible", True):
        continue
    _houdini_cli_network_categories = _houdini_cli_tool.get("network_categories", [])
    if (
        _houdini_cli_category_name not in _houdini_cli_network_categories
        and _houdini_cli_category_name != _houdini_cli_properties.get("nodetype_category")
    ):
        continue
    _houdini_cli_label = str(_houdini_cli_type.description())
    _houdini_cli_items.append({
        "key": str(_houdini_cli_key),
        "description": _houdini_cli_label + " (recipe)",
        "label": _houdini_cli_label,
        "kind": "recipe",
        "icon": str(_houdini_cli_tool.get("icon") or _houdini_cli_type.icon()),
        "submenus": [str(_houdini_cli_value) for _houdini_cli_value in _houdini_cli_tool.get("tab_submenus", [])],
        "recipe_category": str(_houdini_cli_properties["recipe_category"]),
    })
_houdini_cli_discovery_json = _houdini_cli_json.dumps(_houdini_cli_items)
"""

_BULK_GET_CODE = """
import json as _houdini_cli_json
import hou

_houdini_cli_category = {
    "obj": hou.objNodeTypeCategory,
    "sop": hou.sopNodeTypeCategory,
    "cop": hou.copNodeTypeCategory,
    "vop": hou.vopNodeTypeCategory,
    "rop": hou.ropNodeTypeCategory,
    "lop": hou.lopNodeTypeCategory,
    "dop": hou.dopNodeTypeCategory,
    "shop": hou.shopNodeTypeCategory,
}[_houdini_cli_category_key]()
_houdini_cli_type = _houdini_cli_category.nodeTypes().get(_houdini_cli_type_key)
_houdini_cli_item = None
if _houdini_cli_type is not None:
    _houdini_cli_item = {
        "key": str(_houdini_cli_type.name()),
        "name": str(_houdini_cli_type.name()),
        "description": str(_houdini_cli_type.description()),
        "category": _houdini_cli_category_key,
        "icon": str(_houdini_cli_type.icon()),
        "hidden": bool(_houdini_cli_type.hidden()),
        "deprecated": bool(_houdini_cli_type.deprecated()),
        "namespace_order": [str(_houdini_cli_name) for _houdini_cli_name in _houdini_cli_type.namespaceOrder()],
        "min_num_inputs": int(_houdini_cli_type.minNumInputs()),
        "max_num_inputs": int(_houdini_cli_type.maxNumInputs()),
        "is_generator": bool(_houdini_cli_type.isGenerator()),
        "kind": "node",
    }
_houdini_cli_get_json = _houdini_cli_json.dumps(_houdini_cli_item)
"""


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    nodetype_parser = subparsers.add_parser("nodetype", help="Discover node types available for creation.")
    nodetype_subparsers = nodetype_parser.add_subparsers(dest="nodetype_command", required=True)

    list_parser = nodetype_subparsers.add_parser("list", help="List node types in one category.")
    list_parser.add_argument("--category", choices=VALID_CATEGORIES, required=True, help="Houdini node type category.")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum number of node types to return (default: {DEFAULT_LIMIT}).",
    )
    list_parser.set_defaults(handler=handle_list)

    find_parser = nodetype_subparsers.add_parser("find", help="Search node types in one category.")
    find_parser.add_argument("--category", choices=VALID_CATEGORIES, required=True, help="Houdini node type category.")
    find_parser.add_argument("--query", help="Case-insensitive substring match against key and description.")
    find_parser.add_argument("--prefix", help="Case-insensitive prefix match against the type key.")
    find_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum number of node types to return (default: {DEFAULT_LIMIT}).",
    )
    find_parser.set_defaults(handler=handle_find)

    get_parser = nodetype_subparsers.add_parser("get", help="Get full metadata for one node type.")
    get_parser.add_argument("--category", choices=VALID_CATEGORIES, required=True, help="Houdini node type category.")
    get_parser.add_argument("type_key", help="Canonical Houdini node type key.")
    get_parser.set_defaults(handler=handle_get)


def _get_category(session: Any, category_key: str) -> Any:
    mapping = {
        "obj": session.hou.objNodeTypeCategory,
        "sop": session.hou.sopNodeTypeCategory,
        "cop": session.hou.copNodeTypeCategory,
        "vop": session.hou.vopNodeTypeCategory,
        "rop": session.hou.ropNodeTypeCategory,
        "lop": session.hou.lopNodeTypeCategory,
        "dop": session.hou.dopNodeTypeCategory,
        "shop": session.hou.shopNodeTypeCategory,
    }
    return mapping[category_key]()


def _node_type_items(category: Any) -> list[tuple[str, Any]]:
    items = [(str(key), node_type) for key, node_type in category.nodeTypes().items()]
    items.sort(key=lambda item: item[0].lower())
    return items


def _compact_item(key: str, node_type: Any) -> dict:
    return {
        "key": key,
        "description": str(node_type.description()),
        "kind": "node",
    }


def _full_item(category_key: str, node_type: Any) -> dict:
    return {
        "key": str(node_type.name()),
        "name": str(node_type.name()),
        "description": str(node_type.description()),
        "category": category_key,
        "icon": str(node_type.icon()),
        "hidden": bool(node_type.hidden()),
        "deprecated": bool(node_type.deprecated()),
        "namespace_order": [str(name) for name in node_type.namespaceOrder()],
        "min_num_inputs": int(node_type.minNumInputs()),
        "max_num_inputs": int(node_type.maxNumInputs()),
        "is_generator": bool(node_type.isGenerator()),
        "kind": "node",
    }


def _category_name(category: Any) -> str:
    return str(category.name())


def _discovery_items(session: Any, category_key: str) -> list[dict[str, Any]]:
    connection = getattr(session, "connection", None)
    if connection is not None:
        namespace = connection.namespace
        namespace["_houdini_cli_category_key"] = category_key
        connection.execute(_BULK_DISCOVERY_CODE)
        items = json.loads(localize(namespace["_houdini_cli_discovery_json"]))
        items.sort(key=lambda item: (item["description"].lower(), item["key"].lower()))
        return items

    category = _get_category(session, category_key)
    items = [_compact_item(key, node_type) for key, node_type in _node_type_items(category)]
    items.extend(tool_recipe_items(session, _category_name(category)))
    items.sort(key=lambda item: (item["description"].lower(), item["key"].lower()))
    return items


def _validate_limit(limit: int) -> None:
    if limit <= 0:
        raise ValueError(f"Limit must be positive: {limit}")


def _filter_items(items: list[dict[str, Any]], query: str | None, prefix: str | None) -> list[dict[str, Any]]:
    query_text = query.strip().lower() if query else None
    prefix_text = prefix.strip().lower() if prefix else None

    if not query_text and not prefix_text:
        raise ValueError("nodetype find requires --query and/or --prefix")

    filtered = []
    for item in items:
        key = item["key"]
        key_lower = key.lower()
        description_lower = item["description"].lower()
        if query_text and query_text not in key_lower and query_text not in description_lower:
            continue
        if prefix_text and not key_lower.startswith(prefix_text):
            continue
        filtered.append(item)
    return filtered


def _list_result(category_key: str, matched_items: list[dict[str, Any]], limit: int) -> dict:
    _validate_limit(limit)
    total_matches = len(matched_items)
    sliced = matched_items[:limit]
    return success_result(
        {
            "category": category_key,
            "count": len(sliced),
            "items": sliced,
        },
        meta={
            "truncated": total_matches > limit,
            "limit": limit,
            "total_matches": total_matches,
            "next_hint": "Refine with --query, --prefix, or increase --limit",
        },
    )


def handle_list(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        items = _discovery_items(session, args.category)
        return _list_result(args.category, items, args.limit)


def handle_find(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        items = _discovery_items(session, args.category)
        filtered = _filter_items(items, args.query, args.prefix)
        return _list_result(args.category, filtered, args.limit)


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        connection = getattr(session, "connection", None)
        if connection is not None:
            namespace = connection.namespace
            namespace["_houdini_cli_category_key"] = args.category
            namespace["_houdini_cli_type_key"] = args.type_key
            connection.execute(_BULK_GET_CODE)
            item = json.loads(localize(namespace["_houdini_cli_get_json"]))
            if item is not None:
                return success_result(item)
            recipe = next(
                (row for row in _discovery_items(session, args.category) if row["key"] == args.type_key),
                None,
            )
            if recipe is not None:
                return success_result({**recipe, "category": args.category})
            raise ValueError(f"Node type or tool recipe not found: category={args.category} key={args.type_key}")

        category = _get_category(session, args.category)
        node_type = category.nodeTypes().get(args.type_key)
        if node_type is not None:
            return success_result(_full_item(args.category, node_type))
        recipe = next(
            (item for item in tool_recipe_items(session, _category_name(category)) if item["key"] == args.type_key),
            None,
        )
        if recipe is not None:
            return success_result({**recipe, "category": args.category})
        raise ValueError(f"Node type or tool recipe not found: category={args.category} key={args.type_key}")
