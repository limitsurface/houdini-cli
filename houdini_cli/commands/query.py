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


def register_parser(node_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    list_parser = node_subparsers.add_parser("list", help="List nodes under a root.")
    list_parser.add_argument("root_path", help="Root node path.")
    list_parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    list_parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    list_parser.set_defaults(handler=handle_list)

    find_parser = node_subparsers.add_parser("find", help="Find nodes under a root.")
    find_parser.add_argument("root_path", help="Root node path.")
    find_parser.add_argument("--type", dest="type_name")
    find_parser.add_argument("--category")
    find_parser.add_argument("--name")
    find_parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    find_parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    find_parser.set_defaults(handler=handle_find)

    summary_parser = node_subparsers.add_parser("summary", help="Summarize a network.")
    summary_parser.add_argument("root_path", help="Root node path.")
    summary_parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    summary_parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    summary_parser.set_defaults(handler=handle_summary)

    inspect_parser = node_subparsers.add_parser("inspect", help="Inspect one node with a focused summary.")
    inspect_parser.add_argument("node_path", help="Node path to inspect.")
    inspect_parser.set_defaults(handler=handle_inspect)


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


def handle_list(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, TRAVERSAL_TIMEOUT_SECONDS):
            root = get_node(session, args.root_path)
            nodes, truncated = _traverse(root, args.max_depth, args.max_nodes)
            items = [node_summary(node) for node in nodes[1:]]
            return success_result(
                {
                    "root": args.root_path,
                    "count": len(items),
                    "items": items,
                },
                meta={
                    "truncated": truncated,
                    "max_nodes": args.max_nodes,
                    "max_depth": args.max_depth,
                },
            )


def handle_find(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, TRAVERSAL_TIMEOUT_SECONDS):
            root = get_node(session, args.root_path)
            nodes, truncated = _traverse(root, args.max_depth, args.max_nodes)
            items = [
                node_summary(node)
                for node in nodes[1:]
                if _match(node, type_name=args.type_name, category=args.category, name=args.name)
            ]
            return success_result(
                {
                    "root": args.root_path,
                    "count": len(items),
                    "items": items,
                },
                meta={
                    "truncated": truncated,
                    "max_nodes": args.max_nodes,
                    "max_depth": args.max_depth,
                },
            )


def handle_summary(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, TRAVERSAL_TIMEOUT_SECONDS):
            root = get_node(session, args.root_path)
            nodes, truncated = _traverse(root, args.max_depth, args.max_nodes)
            descendants = nodes[1:]
            type_histogram = Counter(node_summary(node)["type"] for node in descendants)
            terminal_nodes = [
                node_summary(node)["path"]
                for node in descendants
                if node_summary(node)["output_count"] == 0
            ][:10]
            entry_nodes = [
                node_summary(node)["path"]
                for node in descendants
                if node_summary(node)["input_count"] == 0
            ][:10]
            return success_result(
                {
                    "root": args.root_path,
                    "node_count": len(descendants),
                    "type_histogram": dict(type_histogram),
                    "entry_nodes": entry_nodes,
                    "terminal_nodes": terminal_nodes,
                },
                meta={
                    "truncated": truncated,
                    "max_nodes": args.max_nodes,
                    "max_depth": args.max_depth,
                },
            )


def handle_inspect(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, TRAVERSAL_TIMEOUT_SECONDS):
            node = get_node(session, args.node_path)
            summary = node_summary(node)
            summary["interesting_parms"] = [
                localize(parm.name())
                for parm in node.parms()[:10]
                if not bool(localize(parm.isAtDefault()))
            ]
            return success_result(summary)
