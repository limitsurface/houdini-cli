"""Structured built-in help commands."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result

HELP_RULES = [
    "stdout is JSON",
    "prefer structured commands before eval",
    "prefer stdin for complex JSON payloads",
    "traversal is summary-first by default",
]

HELP_NOTES = [
    "rpyc 5.x is required with the current Houdini/hrpyc pairing",
    "complex JSON should usually go through stdin with --json -",
    "component parm reads may return tuple-shaped data",
    "node get --section parms may return null",
    "attrib get is summary-first by default and caps sampled values unless --element is used",
    "aggregate attribute stats are intentionally out of scope for now; use SOP/VEX-side analysis when needed",
    "detail attributes do not accept --element",
    "nodetype list and nodetype find are intentionally compact and capped by default",
]

HELP_TREE = {
    "ping": {
        "usage": "houdini-cli ping",
        "examples": ["uv run houdini-cli ping"],
    },
    "eval": {
        "usage": "houdini-cli eval --code <python>",
        "examples": ['uv run houdini-cli eval --code "print(hou.applicationVersionString())"'],
    },
    "parm": {
        "children": {
            "get": {
                "usage": "houdini-cli parm get <parm-path> [--full]",
                "examples": ["uv run houdini-cli parm get /obj/cli_attrib_live/box1/sizex"],
            },
            "set": {
                "usage": "houdini-cli parm set <parm-path> --json <payload-or-'-'> [--full]",
                "examples": [
                    'uv run houdini-cli parm set /obj/cli_attrib_live/box1/sizex --json "2.5"',
                    '\'{"value":[1,2,3]}\' | uv run houdini-cli parm set /obj/cli_attrib_live/box1/t --full --json -',
                ],
            },
        }
    },
    "node": {
        "children": {
            "create": {"usage": "houdini-cli node create <parent-path> <node-type> [--name <node-name>]"},
            "delete": {"usage": "houdini-cli node delete <node-path>"},
            "get": {
                "usage": "houdini-cli node get <node-path> [--section parms|inputs|full]",
                "examples": ["uv run houdini-cli node get /obj/cli_attrib_live/OUT --section inputs"],
            },
            "set": {
                "usage": "houdini-cli node set <node-path> --section parms|inputs|full --json <payload-or-'-'>",
            },
            "list": {"usage": "houdini-cli node list <root-path> [--max-depth N] [--max-nodes N]"},
            "find": {"usage": "houdini-cli node find <root-path> [--type TYPE] [--category CATEGORY] [--name TEXT]"},
            "summary": {"usage": "houdini-cli node summary <root-path> [--max-depth N] [--max-nodes N]"},
            "inspect": {"usage": "houdini-cli node inspect <node-path>"},
            "nav": {
                "usage": "houdini-cli node nav <node-path> [<node-path> ...] [--no-frame] [--no-select] [--no-current]",
                "notes": ["requires shared parent network and graphical Houdini UI"],
            },
        }
    },
    "attrib": {
        "children": {
            "list": {"usage": "houdini-cli attrib list <node-path> [--class point|prim|vertex|detail]"},
            "get": {
                "usage": "houdini-cli attrib get <node-path> <attrib-name> --class point|prim|vertex|detail [--element N] [--limit N]",
            },
        }
    },
    "nodetype": {
        "children": {
            "list": {"usage": "houdini-cli nodetype list --category obj|sop|cop|vop|rop|lop|dop|shop [--limit N]"},
            "find": {
                "usage": "houdini-cli nodetype find --category obj|sop|cop|vop|rop|lop|dop|shop (--query TEXT | --prefix TEXT) [--limit N]",
            },
            "get": {"usage": "houdini-cli nodetype get --category obj|sop|cop|vop|rop|lop|dop|shop <type-key>"},
        }
    },
}


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
            "notes": HELP_NOTES,
        }

    node = _find_help_node(command_path)
    payload = {"path": command_path}
    if "usage" in node:
        payload["usage"] = node["usage"]
    if "examples" in node:
        payload["examples"] = node["examples"]
    if "notes" in node:
        payload["notes"] = node["notes"]
    if "children" in node:
        payload["subcommands"] = sorted(node["children"].keys())
    return payload


def handle_help(args: argparse.Namespace) -> dict:
    return success_result(_topic_payload(args.command_path))
