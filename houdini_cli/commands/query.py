"""Traversal and query commands."""

from __future__ import annotations

import argparse
from collections import Counter, deque
from typing import Any

from ..format.envelopes import success_result
from ..runtime.timeouts import TRAVERSAL_TIMEOUT_SECONDS
from ..transport.rpyc import connect, localize, sync_request_timeout
from .node_common import get_node, node_summary

DEFAULT_MAX_NODES = 50
DEFAULT_MAX_DEPTH = 1
SUMMARY_DEFAULT_MAX_NODES = 10_000
DEFAULT_TOP_TYPES = 20
BOUNDARY_ROW_LIMIT = 50

_QUERY_DISCOVERY_CODE = r"""
import hou
from collections import deque as _houdini_cli_deque

def _houdini_cli_relative_path(root_path, node_path):
    if node_path == root_path:
        return "."
    root_prefix = root_path.rstrip("/") + "/"
    if node_path.startswith(root_prefix):
        return node_path[len(root_prefix):]
    return node_path

def _houdini_cli_flags(node):
    return "".join([
        "d" if hasattr(node, "isDisplayFlagSet") and node.isDisplayFlagSet() else "",
        "r" if hasattr(node, "isRenderFlagSet") and node.isRenderFlagSet() else "",
        "b" if hasattr(node, "isBypassed") and node.isBypassed() else "",
    ])

def _houdini_cli_compact_row(root_path, node):
    inputs = node.inputs()
    return [
        _houdini_cli_relative_path(root_path, node.path()),
        node.type().name(),
        len(node.children()),
        len([item for item in inputs if item is not None]),
        len(node.outputs()),
        _houdini_cli_flags(node),
    ]

def _houdini_cli_query_rows(root_path, max_depth, max_nodes, type_name=None, category=None, name=None):
    root = hou.node(root_path)
    if root is None:
        raise ValueError("Node not found: " + root_path)
    queue = _houdini_cli_deque([(root, 0)])
    nodes = []
    truncated = False
    while queue:
        node, depth = queue.popleft()
        if depth > max_depth:
            continue
        nodes.append(node)
        if len(nodes) >= max_nodes:
            truncated = True
            break
        for child in node.children():
            queue.append((child, depth + 1))

    rows = []
    needle = name.lower() if name else None
    for node in nodes[1:]:
        if type_name and node.type().name() != type_name:
            continue
        if category and node.type().category().name() != category:
            continue
        if needle and needle not in node.name().lower():
            continue
        rows.append(_houdini_cli_compact_row(root_path, node))
    return {"rows": rows, "truncated": truncated}

def _houdini_cli_query_count(root_path, max_depth, max_nodes, type_name=None, category=None, name=None):
    root = hou.node(root_path)
    if root is None:
        raise ValueError("Node not found: " + root_path)
    queue = _houdini_cli_deque([(root, 0)])
    visited = 0
    count = 0
    truncated = False
    needle = name.lower() if name else None
    while queue:
        node, depth = queue.popleft()
        if depth > max_depth:
            continue
        visited += 1
        if node is not root:
            if type_name and node.type().name() != type_name:
                pass
            elif category and node.type().category().name() != category:
                pass
            elif needle and needle not in node.name().lower():
                pass
            else:
                count += 1
        if visited >= max_nodes:
            truncated = True
            break
        for child in node.children():
            queue.append((child, depth + 1))
    return {"count": count, "truncated": truncated}

def _houdini_cli_ordered_graph_neighbors(node, direction):
    neighbors = []
    if direction in ("both", "upstream"):
        connections = []
        for connection in node.inputConnections():
            other = connection.inputNode()
            if other is not None:
                connections.append((int(connection.inputIndex()), int(connection.outputIndex()), other.path(), other))
        connections.sort(key=lambda item: (item[0], item[1], item[2]))
        neighbors.extend(item[3] for item in connections)
    if direction in ("both", "downstream"):
        connections = []
        for connection in node.outputConnections():
            other = connection.outputNode()
            if other is not None:
                connections.append((int(connection.outputIndex()), int(connection.inputIndex()), other.path(), other))
        connections.sort(key=lambda item: (item[0], item[1], item[2]))
        neighbors.extend(item[3] for item in connections)
    result = []
    seen = set()
    for other in neighbors:
        path = other.path()
        if path not in seen:
            seen.add(path)
            result.append(other)
    return result

def _houdini_cli_neighbor_rows(node_path, direction, depth_limit, max_nodes):
    root = hou.node(node_path)
    if root is None:
        raise ValueError("Node not found: " + node_path)
    queue = _houdini_cli_deque([(root, 0)])
    enqueued = {root.path()}
    nodes = []
    truncated = False
    while queue:
        node, depth = queue.popleft()
        nodes.append(node)
        if depth >= depth_limit:
            continue
        for other in _houdini_cli_ordered_graph_neighbors(node, direction):
            path = other.path()
            if path in enqueued:
                continue
            if len(enqueued) >= max_nodes:
                truncated = True
                continue
            enqueued.add(path)
            queue.append((other, depth + 1))

    index_by_path = {node.path(): idx for idx, node in enumerate(nodes)}
    node_rows = []
    edge_rows = set()
    root_parent = node_path.rsplit("/", 1)[0] or "/"
    for idx, node in enumerate(nodes):
        node_rows.append([
            idx,
            _houdini_cli_relative_path(root_parent, node.path()),
            node.type().name(),
            _houdini_cli_flags(node),
        ])
        for connection in node.inputConnections():
            source = connection.inputNode()
            dest = connection.outputNode()
            if source is None or dest is None:
                continue
            source_path = source.path()
            dest_path = dest.path()
            if source_path not in index_by_path or dest_path not in index_by_path:
                continue
            edge_rows.add((
                index_by_path[source_path],
                int(connection.outputIndex()),
                index_by_path[dest_path],
                int(connection.inputIndex()),
            ))
    return {"node_rows": node_rows, "edge_rows": [list(row) for row in sorted(edge_rows)], "truncated": truncated}

def _houdini_cli_network_nodes(root, max_depth, max_nodes):
    queue = _houdini_cli_deque()
    for child in sorted(root.children(), key=lambda item: item.path()):
        queue.append((child, 1))
    nodes = []
    truncated = False
    while queue:
        node, depth = queue.popleft()
        if depth > max_depth:
            continue
        if len(nodes) >= max_nodes:
            truncated = True
            break
        nodes.append(node)
        if depth < max_depth:
            for child in sorted(node.children(), key=lambda item: item.path()):
                queue.append((child, depth + 1))
    return nodes, truncated

def _houdini_cli_message_count(node, method_name):
    method = getattr(node, method_name, None)
    if method is None:
        return 0
    try:
        return len(method())
    except Exception:
        return 0

def _houdini_cli_is_native_network(node):
    if not hasattr(node, "isNetwork") or not node.isNetwork():
        return False
    definition_method = getattr(node.type(), "definition", None)
    return definition_method is None or definition_method() is None

def _houdini_cli_boundary_table(root_path, rows, limit):
    rows.sort(key=lambda row: row[0].lower())
    return {
        "count": len(rows),
        "cols": ["p", "t"],
        "rows": rows[:limit],
        "truncated": len(rows) > limit,
        "limit": limit,
    }

def _houdini_cli_network_summary(root_path, max_depth, max_nodes, top_types, include_boundaries, boundary_limit):
    root = hou.node(root_path)
    if root is None:
        raise ValueError("Node not found: " + root_path)
    nodes, truncated = _houdini_cli_network_nodes(root, max_depth, max_nodes)
    type_counts = {}
    category_counts = {}
    counts = {
        "nodes": len(nodes),
        "subnets": 0,
        "bypassed": 0,
        "display": 0,
        "render": 0,
        "with_errors": 0,
        "with_warnings": 0,
    }
    for node in nodes:
        type_name = node.type().name()
        category_name = node.type().category().name()
        type_counts[type_name] = type_counts.get(type_name, 0) + 1
        category_counts[category_name] = category_counts.get(category_name, 0) + 1
        counts["subnets"] += int(_houdini_cli_is_native_network(node))
        counts["bypassed"] += int(hasattr(node, "isBypassed") and bool(node.isBypassed()))
        counts["display"] += int(hasattr(node, "isDisplayFlagSet") and bool(node.isDisplayFlagSet()))
        counts["render"] += int(hasattr(node, "isRenderFlagSet") and bool(node.isRenderFlagSet()))
        counts["with_errors"] += int(_houdini_cli_message_count(node, "errors") > 0)
        counts["with_warnings"] += int(_houdini_cli_message_count(node, "warnings") > 0)

    ordered_types = sorted(type_counts.items(), key=lambda item: (-item[1], item[0].lower()))
    shown_types = ordered_types[:top_types]
    data = {
        "root": root_path,
        "scope": {"max_depth": max_depth, "max_nodes": max_nodes},
        "counts": counts,
        "type_histogram": [{"type": name, "count": count} for name, count in shown_types],
        "type_histogram_other": sum(count for _name, count in ordered_types[top_types:]),
        "category_histogram": [
            {"category": name, "count": count}
            for name, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        ],
    }
    if include_boundaries:
        paths = {node.path() for node in nodes}
        boundary_rows = {"entry_nodes": [], "terminal_nodes": [], "branch_nodes": [], "fan_in_nodes": []}
        for node in nodes:
            inputs = set()
            outputs = set()
            for connection in node.inputConnections():
                other = connection.inputNode()
                if other is not None and other.path() in paths:
                    inputs.add((other.path(), int(connection.outputIndex()), int(connection.inputIndex())))
            for connection in node.outputConnections():
                other = connection.outputNode()
                if other is not None and other.path() in paths:
                    outputs.add((other.path(), int(connection.outputIndex()), int(connection.inputIndex())))
            row = [_houdini_cli_relative_path(root_path, node.path()), node.type().name()]
            if not inputs:
                boundary_rows["entry_nodes"].append(row)
            if not outputs:
                boundary_rows["terminal_nodes"].append(row)
            if len(outputs) > 1:
                boundary_rows["branch_nodes"].append(row)
            if len(inputs) > 1:
                boundary_rows["fan_in_nodes"].append(row)
        data["boundaries"] = {
            name: _houdini_cli_boundary_table(root_path, rows, boundary_limit)
            for name, rows in boundary_rows.items()
        }
    return {
        "data": data,
        "meta": {
            "truncated": truncated,
            "visited_nodes": len(nodes),
            "max_nodes": max_nodes,
            "max_depth": max_depth,
            "top_types": top_types,
        },
    }
"""


def register_parser(node_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    list_parser = node_subparsers.add_parser("list", help="List nodes under a root.")
    list_parser.add_argument("root_path", help="Root node path.")
    list_parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    list_parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    list_parser.add_argument(
        "--count-only",
        action="store_true",
        help="Return only the number of nodes matching the bounded traversal.",
    )
    list_parser.set_defaults(handler=handle_list)

    summary_parser = node_subparsers.add_parser("summary", help="Summarize a network without returning every node.")
    summary_parser.add_argument("root_path", help="Root network node path.")
    summary_parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    summary_parser.add_argument("--max-nodes", type=int, default=SUMMARY_DEFAULT_MAX_NODES)
    summary_parser.add_argument("--top-types", type=int, default=DEFAULT_TOP_TYPES)
    summary_parser.add_argument(
        "--include-boundaries",
        action="store_true",
        help="Include bounded structural entry, terminal, branch, and fan-in node lists.",
    )
    summary_parser.set_defaults(handler=handle_summary)

    find_parser = node_subparsers.add_parser("find", help="Find nodes under a root.")
    find_parser.add_argument("root_path", help="Root node path.")
    find_parser.add_argument("--type", dest="type_name")
    find_parser.add_argument("--category")
    find_parser.add_argument("--name")
    find_parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    find_parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    find_parser.set_defaults(handler=handle_find)

    neighbors_parser = node_subparsers.add_parser("neighbors", help="Inspect local graph neighbors for one node.")
    neighbors_parser.add_argument("node_path", help="Node path to inspect.")
    neighbors_parser.add_argument(
        "--direction",
        choices=("both", "upstream", "downstream"),
        default="both",
        help="Graph direction to traverse (default: both).",
    )
    neighbors_parser.add_argument("--depth", type=int, default=1, help="Neighbor traversal depth.")
    neighbors_parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    neighbors_parser.set_defaults(handler=handle_neighbors)


def _traverse(root: Any, max_depth: int, max_nodes: int) -> tuple[list[Any], bool]:
    queue = deque([(root, 0)])
    nodes: list[Any] = []
    truncated = False

    while queue:
        node, depth = queue.popleft()
        if depth > max_depth:
            continue
        nodes.append(node)
        if len(nodes) >= max_nodes:
            truncated = True
            break
        for child in node.children():
            queue.append((child, depth + 1))

    return nodes, truncated


def _match(node: Any, *, type_name: str | None, category: str | None, name: str | None) -> bool:
    summary = node_summary(node)
    if type_name and summary["type"] != type_name:
        return False
    if category and summary["category"] != category:
        return False
    if name and name.lower() not in summary["name"].lower():
        return False
    return True


def _relative_path(root_path: str, node_path: str) -> str:
    if node_path == root_path:
        return "."
    root_prefix = root_path.rstrip("/") + "/"
    if node_path.startswith(root_prefix):
        return node_path[len(root_prefix) :]
    return node_path


def _flags(summary: dict[str, Any]) -> str:
    return "".join(
        [
            "d" if summary.get("display") else "",
            "r" if summary.get("render") else "",
            "b" if summary.get("bypass") else "",
        ]
    )


def _compact_row(root_path: str, node: Any) -> list[Any]:
    summary = node_summary(node)
    return [
        _relative_path(root_path, summary["path"]),
        summary["type"],
        summary["child_count"],
        summary["input_count"],
        summary["output_count"],
        _flags(summary),
    ]


def _validate_traversal_limits(*, max_depth: int, max_nodes: int) -> None:
    if max_depth < 0:
        raise ValueError("max depth must be zero or greater")
    if max_nodes < 1:
        raise ValueError("max nodes must be at least one")


def _ordered_graph_neighbors(node: Any, direction: str) -> list[Any]:
    ordered: list[tuple[tuple[Any, ...], Any]] = []
    if direction in {"both", "upstream"}:
        connections = getattr(node, "inputConnections", lambda: ())()
        for connection in connections:
            other = connection.inputNode()
            if other is None:
                continue
            ordered.append(
                (
                    (
                        0,
                        int(localize(connection.inputIndex())),
                        int(localize(connection.outputIndex())),
                        localize(other.path()),
                    ),
                    other,
                )
            )
    if direction in {"both", "downstream"}:
        output_connections = getattr(node, "outputConnections", None)
        if callable(output_connections):
            for connection in output_connections():
                other = connection.outputNode()
                if other is None:
                    continue
                ordered.append(
                    (
                        (
                            1,
                            int(localize(connection.outputIndex())),
                            int(localize(connection.inputIndex())),
                            localize(other.path()),
                        ),
                        other,
                    )
                )
        else:
            for index, other in enumerate(node.outputs()):
                if other is not None:
                    ordered.append(((1, index, 0, localize(other.path())), other))

    result: list[Any] = []
    seen: set[str] = set()
    for _key, other in sorted(ordered, key=lambda item: item[0]):
        path = localize(other.path())
        if path not in seen:
            seen.add(path)
            result.append(other)
    return result


def _graph_nodes(root: Any, *, direction: str, depth_limit: int, max_nodes: int) -> tuple[list[Any], bool]:
    queue = deque([(root, 0)])
    enqueued = {localize(root.path())}
    nodes: list[Any] = []
    truncated = False
    while queue:
        node, depth = queue.popleft()
        nodes.append(node)
        if depth >= depth_limit:
            continue
        for other in _ordered_graph_neighbors(node, direction):
            path = localize(other.path())
            if path in enqueued:
                continue
            if len(enqueued) >= max_nodes:
                truncated = True
                continue
            enqueued.add(path)
            queue.append((other, depth + 1))
    return nodes, truncated


def _graph_rows(root_path: str, nodes: list[Any]) -> tuple[list[list[Any]], list[list[int]]]:
    index_by_path = {localize(node.path()): index for index, node in enumerate(nodes)}
    root_parent = root_path.rsplit("/", 1)[0] or "/"
    node_rows: list[list[Any]] = []
    edge_rows: set[tuple[int, int, int, int]] = set()
    for index, node in enumerate(nodes):
        summary = node_summary(node)
        node_rows.append(
            [index, _relative_path(root_parent, summary["path"]), summary["type"], _flags(summary)]
        )
        for connection in node.inputConnections():
            source = connection.inputNode()
            dest = connection.outputNode()
            if source is None or dest is None:
                continue
            source_path = localize(source.path())
            dest_path = localize(dest.path())
            if source_path not in index_by_path or dest_path not in index_by_path:
                continue
            edge_rows.add(
                (
                    index_by_path[source_path],
                    int(localize(connection.outputIndex())),
                    index_by_path[dest_path],
                    int(localize(connection.inputIndex())),
                )
            )
    return node_rows, [list(row) for row in sorted(edge_rows)]


def _network_nodes(root: Any, *, max_depth: int, max_nodes: int) -> tuple[list[Any], bool]:
    queue = deque((child, 1) for child in sorted(root.children(), key=lambda item: localize(item.path())))
    nodes: list[Any] = []
    truncated = False
    while queue:
        node, depth = queue.popleft()
        if depth > max_depth:
            continue
        if len(nodes) >= max_nodes:
            truncated = True
            break
        nodes.append(node)
        if depth < max_depth:
            for child in sorted(node.children(), key=lambda item: localize(item.path())):
                queue.append((child, depth + 1))
    return nodes, truncated


def _message_count(node: Any, method_name: str) -> int:
    method = getattr(node, method_name, None)
    if not callable(method):
        return 0
    try:
        return len(localize(method()))
    except Exception:
        return 0


def _is_native_network(node: Any) -> bool:
    is_network = getattr(node, "isNetwork", None)
    if not callable(is_network):
        return bool(node.children())
    if not bool(localize(is_network())):
        return False
    definition = getattr(node.type(), "definition", None)
    return not callable(definition) or localize(definition()) is None


def _output_connections(node: Any) -> list[Any]:
    method = getattr(node, "outputConnections", None)
    return list(method()) if callable(method) else []


def _boundary_table(rows: list[list[str]]) -> dict[str, Any]:
    rows.sort(key=lambda row: row[0].lower())
    return {
        "count": len(rows),
        "cols": ["p", "t"],
        "rows": rows[:BOUNDARY_ROW_LIMIT],
        "truncated": len(rows) > BOUNDARY_ROW_LIMIT,
        "limit": BOUNDARY_ROW_LIMIT,
    }


def _network_summary_payload(
    root_path: str,
    nodes: list[Any],
    *,
    max_depth: int,
    max_nodes: int,
    top_types: int,
    include_boundaries: bool,
) -> dict[str, Any]:
    summaries = [node_summary(node) for node in nodes]
    type_counts = Counter(summary["type"] for summary in summaries)
    category_counts = Counter(summary["category"] for summary in summaries)
    ordered_types = sorted(type_counts.items(), key=lambda item: (-item[1], item[0].lower()))
    payload: dict[str, Any] = {
        "root": root_path,
        "scope": {"max_depth": max_depth, "max_nodes": max_nodes},
        "counts": {
            "nodes": len(nodes),
            "subnets": sum(_is_native_network(node) for node in nodes),
            "bypassed": sum(bool(summary.get("bypass")) for summary in summaries),
            "display": sum(bool(summary.get("display")) for summary in summaries),
            "render": sum(bool(summary.get("render")) for summary in summaries),
            "with_errors": sum(_message_count(node, "errors") > 0 for node in nodes),
            "with_warnings": sum(_message_count(node, "warnings") > 0 for node in nodes),
        },
        "type_histogram": [
            {"type": name, "count": count} for name, count in ordered_types[:top_types]
        ],
        "type_histogram_other": sum(count for _name, count in ordered_types[top_types:]),
        "category_histogram": [
            {"category": name, "count": count}
            for name, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        ],
    }
    if include_boundaries:
        paths = {localize(node.path()) for node in nodes}
        boundary_rows: dict[str, list[list[str]]] = {
            "entry_nodes": [],
            "terminal_nodes": [],
            "branch_nodes": [],
            "fan_in_nodes": [],
        }
        for node, summary in zip(nodes, summaries):
            inputs = {
                (
                    localize(connection.inputNode().path()),
                    int(localize(connection.outputIndex())),
                    int(localize(connection.inputIndex())),
                )
                for connection in node.inputConnections()
                if connection.inputNode() is not None and localize(connection.inputNode().path()) in paths
            }
            outputs = {
                (
                    localize(connection.outputNode().path()),
                    int(localize(connection.outputIndex())),
                    int(localize(connection.inputIndex())),
                )
                for connection in _output_connections(node)
                if connection.outputNode() is not None and localize(connection.outputNode().path()) in paths
            }
            row = [_relative_path(root_path, summary["path"]), summary["type"]]
            if not inputs:
                boundary_rows["entry_nodes"].append(row)
            if not outputs:
                boundary_rows["terminal_nodes"].append(row)
            if len(outputs) > 1:
                boundary_rows["branch_nodes"].append(row)
            if len(inputs) > 1:
                boundary_rows["fan_in_nodes"].append(row)
        payload["boundaries"] = {
            name: _boundary_table(rows) for name, rows in boundary_rows.items()
        }
    return payload


def _query_rows_in_houdini(
    session: Any,
    *,
    root_path: str,
    max_depth: int,
    max_nodes: int,
    type_name: str | None = None,
    category: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    connection = getattr(session, "connection", None)
    if connection is None:
        return None
    connection.execute(_QUERY_DISCOVERY_CODE)
    return localize(
        connection.eval(
            "_houdini_cli_query_rows("
            f"{root_path!r}, {int(max_depth)!r}, {int(max_nodes)!r}, "
            f"{type_name!r}, {category!r}, {name!r})"
        )
    )


def _query_count_in_houdini(
    session: Any,
    *,
    root_path: str,
    max_depth: int,
    max_nodes: int,
    type_name: str | None = None,
    category: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    connection = getattr(session, "connection", None)
    if connection is None:
        return None
    connection.execute(_QUERY_DISCOVERY_CODE)
    return localize(
        connection.eval(
            "_houdini_cli_query_count("
            f"{root_path!r}, {int(max_depth)!r}, {int(max_nodes)!r}, "
            f"{type_name!r}, {category!r}, {name!r})"
        )
    )


def _neighbor_rows_in_houdini(
    session: Any,
    *,
    node_path: str,
    direction: str,
    depth: int,
    max_nodes: int,
) -> dict[str, Any] | None:
    connection = getattr(session, "connection", None)
    if connection is None:
        return None
    connection.execute(_QUERY_DISCOVERY_CODE)
    return localize(
        connection.eval(
            f"_houdini_cli_neighbor_rows({node_path!r}, {direction!r}, {int(depth)!r}, {int(max_nodes)!r})"
        )
    )


def _network_summary_in_houdini(
    session: Any,
    *,
    root_path: str,
    max_depth: int,
    max_nodes: int,
    top_types: int,
    include_boundaries: bool,
) -> dict[str, Any] | None:
    connection = getattr(session, "connection", None)
    if connection is None:
        return None
    connection.execute(_QUERY_DISCOVERY_CODE)
    return localize(
        connection.eval(
            "_houdini_cli_network_summary("
            f"{root_path!r}, {int(max_depth)!r}, {int(max_nodes)!r}, {int(top_types)!r}, "
            f"{bool(include_boundaries)!r}, {int(BOUNDARY_ROW_LIMIT)!r})"
        )
    )


def handle_list(args: argparse.Namespace) -> dict:
    _validate_traversal_limits(max_depth=args.max_depth, max_nodes=args.max_nodes)
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, TRAVERSAL_TIMEOUT_SECONDS):
            if getattr(args, "count_only", False):
                remote_count = _query_count_in_houdini(
                    session,
                    root_path=args.root_path,
                    max_depth=args.max_depth,
                    max_nodes=args.max_nodes,
                )
                if remote_count is not None:
                    return success_result(
                        {"root": args.root_path, "count": int(remote_count["count"])},
                        meta={
                            "truncated": bool(remote_count["truncated"]),
                            "max_nodes": args.max_nodes,
                            "max_depth": args.max_depth,
                        },
                    )
                root = get_node(session, args.root_path)
                nodes, truncated = _traverse(root, args.max_depth, args.max_nodes)
                return success_result(
                    {"root": args.root_path, "count": max(0, len(nodes) - 1)},
                    meta={
                        "truncated": truncated,
                        "max_nodes": args.max_nodes,
                        "max_depth": args.max_depth,
                    },
                )
            remote = _query_rows_in_houdini(
                session,
                root_path=args.root_path,
                max_depth=args.max_depth,
                max_nodes=args.max_nodes,
            )
            if remote is not None:
                return success_result(
                    {
                        "root": args.root_path,
                        "count": len(remote["rows"]),
                        "cols": ["p", "t", "cc", "in", "out", "f"],
                        "rows": remote["rows"],
                    },
                    meta={
                        "truncated": bool(remote["truncated"]),
                        "max_nodes": args.max_nodes,
                        "max_depth": args.max_depth,
                    },
                )
            root = get_node(session, args.root_path)
            nodes, truncated = _traverse(root, args.max_depth, args.max_nodes)
            rows = [_compact_row(args.root_path, node) for node in nodes[1:]]
            return success_result(
                {
                    "root": args.root_path,
                    "count": len(rows),
                    "cols": ["p", "t", "cc", "in", "out", "f"],
                    "rows": rows,
                },
                meta={
                    "truncated": truncated,
                    "max_nodes": args.max_nodes,
                    "max_depth": args.max_depth,
                },
            )


def handle_summary(args: argparse.Namespace) -> dict:
    _validate_traversal_limits(max_depth=args.max_depth, max_nodes=args.max_nodes)
    if args.top_types < 1:
        raise ValueError("top types must be at least one")
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, TRAVERSAL_TIMEOUT_SECONDS):
            remote = _network_summary_in_houdini(
                session,
                root_path=args.root_path,
                max_depth=args.max_depth,
                max_nodes=args.max_nodes,
                top_types=args.top_types,
                include_boundaries=args.include_boundaries,
            )
            if remote is not None:
                return success_result(remote["data"], meta=remote["meta"])
            root = get_node(session, args.root_path)
            nodes, truncated = _network_nodes(root, max_depth=args.max_depth, max_nodes=args.max_nodes)
            payload = _network_summary_payload(
                args.root_path,
                nodes,
                max_depth=args.max_depth,
                max_nodes=args.max_nodes,
                top_types=args.top_types,
                include_boundaries=args.include_boundaries,
            )
            return success_result(
                payload,
                meta={
                    "truncated": truncated,
                    "visited_nodes": len(nodes),
                    "max_nodes": args.max_nodes,
                    "max_depth": args.max_depth,
                    "top_types": args.top_types,
                },
            )


def handle_find(args: argparse.Namespace) -> dict:
    _validate_traversal_limits(max_depth=args.max_depth, max_nodes=args.max_nodes)
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, TRAVERSAL_TIMEOUT_SECONDS):
            remote = _query_rows_in_houdini(
                session,
                root_path=args.root_path,
                max_depth=args.max_depth,
                max_nodes=args.max_nodes,
                type_name=args.type_name,
                category=args.category,
                name=args.name,
            )
            if remote is not None:
                return success_result(
                    {
                        "root": args.root_path,
                        "query": {
                            key: value
                            for key, value in {
                                "type": args.type_name,
                                "category": args.category,
                                "name": args.name,
                            }.items()
                            if value is not None
                        },
                        "count": len(remote["rows"]),
                        "cols": ["p", "t", "cc", "in", "out", "f"],
                        "rows": remote["rows"],
                    },
                    meta={
                        "truncated": bool(remote["truncated"]),
                        "max_nodes": args.max_nodes,
                        "max_depth": args.max_depth,
                    },
                )
            root = get_node(session, args.root_path)
            nodes, truncated = _traverse(root, args.max_depth, args.max_nodes)
            rows = [
                _compact_row(args.root_path, node)
                for node in nodes[1:]
                if _match(node, type_name=args.type_name, category=args.category, name=args.name)
            ]
            return success_result(
                {
                    "root": args.root_path,
                    "query": {
                        key: value
                        for key, value in {
                            "type": args.type_name,
                            "category": args.category,
                            "name": args.name,
                        }.items()
                        if value is not None
                    },
                    "count": len(rows),
                    "cols": ["p", "t", "cc", "in", "out", "f"],
                    "rows": rows,
                },
                meta={
                    "truncated": truncated,
                    "max_nodes": args.max_nodes,
                    "max_depth": args.max_depth,
                },
            )


def handle_neighbors(args: argparse.Namespace) -> dict:
    direction = getattr(args, "direction", "both")
    _validate_traversal_limits(max_depth=args.depth, max_nodes=args.max_nodes)
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, TRAVERSAL_TIMEOUT_SECONDS):
            remote = _neighbor_rows_in_houdini(
                session,
                node_path=args.node_path,
                direction=direction,
                depth=args.depth,
                max_nodes=args.max_nodes,
            )
            if remote is not None:
                return success_result(
                    {
                        "root": args.node_path,
                        "direction": direction,
                        "depth": args.depth,
                        "nodes": {
                            "cols": ["id", "p", "t", "f"],
                            "rows": remote["node_rows"],
                        },
                        "edges": {
                            "cols": ["src", "out", "dst", "in"],
                            "rows": remote["edge_rows"],
                        },
                    },
                    meta={"truncated": bool(remote["truncated"]), "max_nodes": args.max_nodes},
                )
            root = get_node(session, args.node_path)
            nodes, truncated = _graph_nodes(
                root,
                direction=direction,
                depth_limit=args.depth,
                max_nodes=args.max_nodes,
            )
            node_rows, edge_rows = _graph_rows(args.node_path, nodes)
            return success_result(
                {
                    "root": args.node_path,
                    "direction": direction,
                    "depth": args.depth,
                    "nodes": {
                        "cols": ["id", "p", "t", "f"],
                        "rows": node_rows,
                    },
                    "edges": {
                        "cols": ["src", "out", "dst", "in"],
                        "rows": edge_rows,
                    },
                },
                meta={"truncated": truncated, "max_nodes": args.max_nodes},
            )
