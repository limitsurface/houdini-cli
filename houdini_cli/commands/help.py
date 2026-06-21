"""Structured built-in help commands."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result

HELP_RULES = [
    "stdout is JSON",
    "prefer structured commands before eval",
    "prefer stdin for complex JSON payloads",
    "prefer node find before broad node list traversal in large networks",
]

HELP_NOTES = [
    "rpyc 5.x is required with the current Houdini/hrpyc pairing",
    "complex JSON should usually go through stdin with --json -",
    "component parm reads return component values; node parm discovery collapses tuples by default",
    "node get --section parms may return null",
    "attrib get is summary-first by default and caps sampled values unless --element is used",
    "aggregate attribute stats are intentionally out of scope for now; use SOP/VEX-side analysis when needed",
    "detail attributes do not accept --element",
    "nodetype list and nodetype find are intentionally compact and capped by default",
]

HELP_LEGENDS = {
    "node_rows": {
        "cols": {
            "p": "path",
            "t": "type",
            "cc": "child_count",
            "in": "input_count",
            "out": "output_count",
            "f": "flags",
        },
        "flags": {
            "d": "display",
            "r": "render",
            "b": "bypass",
        },
        "notes": [
            "node list and node find return compact rows",
            "paths are relative to the requested root when possible",
        ],
    },
    "node_neighbors": {
        "nodes_cols": {
            "id": "response-local node id",
            "p": "path",
            "t": "type",
            "f": "flags",
        },
        "edges_cols": {
            "src": "source node id",
            "out": "source output index",
            "dst": "destination node id",
            "in": "destination input index",
        },
        "flags": {
            "d": "display",
            "r": "render",
            "b": "bypass",
        },
        "notes": [
            "neighbor node ids are response-local and only stable within one response",
        ],
    },
    "node_parm_rows": {
        "cols": {
            "p": "parm name",
            "t": "parm template type",
            "v": "current value",
            "f": "flags",
        },
        "flags": {
            "n": "non-default",
        },
        "notes": [
            "node parms list and node parms find skip UI-only folder/button parm templates",
            "tuple parms are collapsed to one row using the tuple name when possible",
        ],
    },
}

from .help_topics import HELP_TREE


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("help", help="Show structured built-in help.")
    parser.add_argument("command_path", nargs="*", help="Optional command path, for example: node nav")
    parser.set_defaults(handler=handle_help)


def _find_help_node(command_path: list[str]) -> dict:
    if not command_path:
        return {}

    current = HELP_TREE
    resolved_path: list[str] = []
    for part in command_path:
        if part not in current:
            joined = " ".join(command_path)
            raise ValueError(f"Help topic not found: {joined}")
        node = current[part]
        resolved_path.append(part)
        current = node.get("children", {})
    return node


def _topic_payload(command_path: list[str]) -> dict:
    if not command_path:
        return {
            "path": [],
            "rules": HELP_RULES,
            "commands": sorted(HELP_TREE.keys()),
            "command_descriptions": {name: node.get("description", "") for name, node in sorted(HELP_TREE.items())},
            "notes": HELP_NOTES,
            "legends": HELP_LEGENDS,
            "workflows": [
                {
                    "task": "After editing an OpenCL kernel",
                    "command": "houdini-cli opencl sync <node-path>",
                },
                {
                    "task": "Check whether OpenCL wires still match regenerated ports",
                    "command": "houdini-cli opencl validate <node-path>",
                },
                {
                    "task": "Inspect explicit node wiring",
                    "command": "houdini-cli node connections <node-path>",
                },
                {
                    "task": "Capture a viewport screenshot",
                    "command": "houdini-cli session screenshot --pane-name <pane>",
                },
                {
                    "task": "Frame the selected object in the viewport",
                    "command": "houdini-cli session viewport focus-selected --pane-name <pane>",
                },
                {
                    "task": "Read which nodes are selected in the UI",
                    "command": "houdini-cli session selection",
                },
                {
                    "task": "Search shelf tools by name",
                    "command": "houdini-cli shelf find --query <text>",
                },
            ],
        }

    node = _find_help_node(command_path)
    payload = {"path": command_path}
    if "description" in node:
        payload["description"] = node["description"]
    if "usage" in node:
        payload["usage"] = node["usage"]
    if "examples" in node:
        payload["examples"] = node["examples"]
    if "notes" in node:
        payload["notes"] = node["notes"]
    if "children" in node:
        payload["subcommands"] = sorted(node["children"].keys())
        payload["subcommand_descriptions"] = {
            name: child.get("description", "")
            for name, child in sorted(node["children"].items())
        }
    return payload


def handle_help(args: argparse.Namespace) -> dict:
    return success_result(_topic_payload(args.command_path))
