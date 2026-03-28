"""Node type discovery commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect

DEFAULT_LIMIT = 50
VALID_CATEGORIES = ("obj", "sop", "cop", "vop", "rop", "lop", "dop", "shop")


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
        "cop": session.hou.cop2NodeTypeCategory,
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
    }


def _validate_limit(limit: int) -> None:
    if limit <= 0:
        raise ValueError(f"Limit must be positive: {limit}")


def _filter_items(items: list[tuple[str, Any]], query: str | None, prefix: str | None) -> list[tuple[str, Any]]:
    query_text = query.strip().lower() if query else None
    prefix_text = prefix.strip().lower() if prefix else None

    if not query_text and not prefix_text:
        raise ValueError("nodetype find requires --query and/or --prefix")

    filtered = []
    for key, node_type in items:
        key_lower = key.lower()
        description_lower = str(node_type.description()).lower()
        if query_text and query_text not in key_lower and query_text not in description_lower:
            continue
        if prefix_text and not key_lower.startswith(prefix_text):
            continue
        filtered.append((key, node_type))
    return filtered


def _list_result(category_key: str, matched_items: list[tuple[str, Any]], limit: int) -> dict:
    _validate_limit(limit)
    total_matches = len(matched_items)
    sliced = matched_items[:limit]
    return success_result(
        {
            "category": category_key,
            "count": len(sliced),
            "items": [_compact_item(key, node_type) for key, node_type in sliced],
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
        category = _get_category(session, args.category)
        items = _node_type_items(category)
        return _list_result(args.category, items, args.limit)


def handle_find(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        category = _get_category(session, args.category)
        items = _node_type_items(category)
        filtered = _filter_items(items, args.query, args.prefix)
        return _list_result(args.category, filtered, args.limit)


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        category = _get_category(session, args.category)
        node_type = category.nodeTypes().get(args.type_key)
        if node_type is None:
            raise ValueError(f"Node type not found: category={args.category} key={args.type_key}")
        return success_result(_full_item(args.category, node_type))
