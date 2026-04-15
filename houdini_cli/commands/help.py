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

HELP_TREE = {
    "ping": {
        "description": "Verify that Houdini is reachable over hrpyc/rpyc.",
        "usage": "houdini-cli ping",
        "examples": ["uv run houdini-cli ping"],
    },
    "session": {
        "description": "Inspect or control session-level state such as connectivity, frame, and viewport screenshots.",
        "children": {
            "ping": {
                "description": "Verify that Houdini is reachable over hrpyc/rpyc.",
                "usage": "houdini-cli session ping",
                "examples": ["uv run houdini-cli session ping"],
            },
            "frame": {
                "description": "Read or set the current timeline frame.",
                "usage": "houdini-cli session frame [<frame>]",
                "examples": [
                    "uv run houdini-cli session frame",
                    "uv run houdini-cli session frame 24",
                ],
            },
            "screenshot": {
                "description": "Capture a screenshot from a specific Scene Viewer pane.",
                "usage": "houdini-cli session screenshot [--pane-name <name> | --index <n>] [--output <path>] [--frame <n>] [--width <px>] [--height <px>]",
                "examples": [
                    "uv run houdini-cli session screenshot --pane-name panetab1",
                    "uv run houdini-cli session screenshot --index 0 --output '$HIP/houdini_cli/screenshots/view.png'",
                ],
                "notes": [
                    "requires graphical Houdini UI",
                    "when multiple Scene Viewers are active, use --pane-name or --index",
                ],
            },
        }
    },
    "eval": {
        "description": "Execute Python against the live Houdini session when no structured command fits.",
        "usage": "houdini-cli eval --code <python>",
        "examples": ['uv run houdini-cli eval --code "print(hou.applicationVersionString())"'],
    },
    "parm": {
        "description": "Read parameter values, structured parameter payloads, menu tokens, and apply parameter edits.",
        "notes": [
            "For OpenCL nodes after kernel edits, prefer: houdini-cli opencl sync <node-path>",
        ],
        "children": {
            "get": {
                "description": "Read the current value for one parameter.",
                "usage": "houdini-cli parm get <parm-path>",
                "examples": ["uv run houdini-cli parm get /obj/cli_attrib_live/box1/sizex"],
            },
            "full": {
                "description": "Read the full structured parameter payload for one parameter.",
                "usage": "houdini-cli parm full <parm-path>",
                "examples": ["uv run houdini-cli parm full /obj/cli_attrib_live/box1/t"],
            },
            "menu": {
                "description": "Inspect the menu items available on a parameter.",
                "usage": "houdini-cli parm menu <parm-path>",
                "examples": ["uv run houdini-cli parm menu /obj/cli_attrib_live/box1/type"],
            },
            "set": {
                "description": "Apply one scalar or string parameter value from a CLI argument.",
                "usage": "houdini-cli parm set <parm-path> <value>",
                "examples": [
                    "uv run houdini-cli parm set /obj/cli_attrib_live/box1/sizex 2.5",
                    "uv run houdini-cli parm set /obj/cli_attrib_live/copytopoints1/applymethod2 mult",
                ],
            },
            "tuple-set": {
                "description": "Set all values on a tuple parameter in tuple order.",
                "usage": "houdini-cli parm tuple-set <parm-path> <value> <value> ...",
                "examples": ["uv run houdini-cli parm tuple-set /obj/cli_attrib_live/xform1/t 1 2 3"],
            },
            "text-set": {
                "description": "Set a text parameter from stdin or a text file.",
                "usage": "houdini-cli parm text-set <parm-path> --input <path-or-'-'>",
                "examples": [
                    "uv run houdini-cli parm text-set /obj/cli_attrib_live/wrangle1/snippet --input snippet.vfl",
                    "Get-Content snippet.vfl | uv run houdini-cli parm text-set /obj/cli_attrib_live/wrangle1/snippet --input -",
                ],
            },
            "full-set": {
                "description": "Apply a full structured parameter payload from stdin or a JSON file.",
                "usage": "houdini-cli parm full-set <parm-path> --input <path-or-'-'>",
                "examples": [
                    "uv run houdini-cli parm full-set /obj/cli_attrib_live/copytopoints1/targetattribs --input payload.json",
                ],
            },
        }
    },
    "node": {
        "description": "Inspect nodes, connections, errors, and apply structured node edits.",
        "notes": [
            "For OpenCL nodes after kernel edits, use: houdini-cli opencl sync <node-path>",
        ],
        "children": {
            "create": {
                "description": "Create a new node under a parent network.",
                "usage": "houdini-cli node create <parent-path> <node-type> [--name <node-name>]",
            },
            "delete": {
                "description": "Delete a node.",
                "usage": "houdini-cli node delete <node-path>",
            },
            "get": {
                "description": "Read a focused node summary or a structured node section.",
                "usage": "houdini-cli node get <node-path> [--section parms|inputs|full]",
                "examples": ["uv run houdini-cli node get /obj/cli_attrib_live/OUT --section inputs"],
            },
            "errors": {
                "description": "Read errors, warnings, and messages from one or more nodes.",
                "usage": "houdini-cli node errors <node-path> [<node-path> ...]",
            },
            "connections": {
                "description": "Read stable explicit input/output connection data for a node.",
                "usage": "houdini-cli node connections <node-path>",
            },
            "set": {
                "description": "Apply structured node data to parms, inputs, or the full node payload.",
                "usage": "houdini-cli node set <node-path> --section parms|inputs|full --json <payload-or-'-'>",
                "notes": [
                    "Use --section parms to batch multiple parameter edits on one node instead of repeating parm set.",
                ],
            },
            "list": {
                "description": "List nodes under a root path in a compact row format with bounded traversal.",
                "usage": "houdini-cli node list <root-path> [--max-depth N] [--max-nodes N]",
                "notes": [
                    "Prefer node find first in large networks; list is best for shallow local traversal.",
                    "See `help` root legends.node_rows for compact field meanings.",
                ],
            },
            "find": {
                "description": "Search for nodes by type, category, or partial name using the same compact row format as list.",
                "usage": "houdini-cli node find <root-path> [--type TYPE] [--category CATEGORY] [--name TEXT] [--max-depth N] [--max-nodes N]",
                "notes": [
                    "Use this as the default discovery tool in large networks before node list.",
                    "See `help` root legends.node_rows for compact field meanings.",
                ],
            },
            "parms": {
                "description": "Discover parameters on one node.",
                "children": {
                    "list": {
                        "description": "List parameters on one node in a compact row format.",
                        "usage": "houdini-cli node parms list <node-path> [--non-default] [--max-parms N]",
                        "notes": [
                            "See `help` root legends.node_parm_rows for compact field meanings.",
                        ],
                    },
                    "find": {
                        "description": "Search parameters on one node in the same compact row format.",
                        "usage": "houdini-cli node parms find <node-path> [--name TEXT] [--type TYPE] [--non-default] [--max-parms N]",
                        "notes": [
                            "See `help` root legends.node_parm_rows for compact field meanings.",
                        ],
                    },
                },
            },
            "neighbors": {
                "description": "Inspect local graph neighbors for one node with compact node and edge tables.",
                "usage": "houdini-cli node neighbors <node-path> [--depth N] [--max-nodes N]",
                "notes": [
                    "See `help` root legends.node_neighbors for compact field meanings.",
                ],
            },
            "nav": {
                "description": "Navigate a Network Editor to one or more nodes.",
                "usage": "houdini-cli node nav <node-path> [<node-path> ...] [--no-frame] [--no-select] [--no-current]",
                "notes": ["requires shared parent network and graphical Houdini UI"],
            },
        }
    },
    "cop": {
        "description": "Inspect cooked Copernicus image/layer data.",
        "children": {
            "sample": {
                "description": "Sample one or more pixel locations from a COP output.",
                "usage": "houdini-cli cop sample <node-path> [--output <index-or-name>] (--x X --y Y | --points <json-or-'-'>)",
            },
        }
    },
    "opencl": {
        "description": "Synchronize OpenCL node bindings, visible signature rows, and generated spare parameters from kernel code.",
        "notes": [
            "After editing an OpenCL kernel, run: houdini-cli opencl sync <node-path>",
            "Use --bindings-only when you want to refresh bindings/parms without changing the visible signature.",
        ],
        "children": {
            "sync": {
                "description": "Refresh an OpenCL node from its kernel #bind directives, including bindings, signature rows, and generated spare parms.",
                "usage": "houdini-cli opencl sync <node-path> [--clear] [--bindings-only]",
                "examples": [
                    "uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1",
                    "uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1 --bindings-only",
                    "uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1 --clear",
                ],
            },
        }
    },
    "attrib": {
        "description": "Inspect geometry attributes with summary-first reads.",
        "children": {
            "list": {
                "description": "List attributes on a node, optionally filtered by class.",
                "usage": "houdini-cli attrib list <node-path> [--class point|prim|vertex|detail]",
            },
            "get": {
                "description": "Read attribute metadata and sampled values.",
                "usage": "houdini-cli attrib get <node-path> <attrib-name> --class point|prim|vertex|detail [--element N] [--limit N]",
            },
        }
    },
    "nodetype": {
        "description": "Discover available node types by category, query, or prefix.",
        "children": {
            "list": {
                "description": "List node types for a category.",
                "usage": "houdini-cli nodetype list --category obj|sop|cop|vop|rop|lop|dop|shop [--limit N]",
            },
            "find": {
                "description": "Search node types by query text or prefix.",
                "usage": "houdini-cli nodetype find --category obj|sop|cop|vop|rop|lop|dop|shop (--query TEXT | --prefix TEXT) [--limit N]",
            },
            "get": {
                "description": "Read details for a specific node type key.",
                "usage": "houdini-cli nodetype get --category obj|sop|cop|vop|rop|lop|dop|shop <type-key>",
            },
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
            "command_descriptions": {name: node.get("description", "") for name, node in sorted(HELP_TREE.items())},
            "notes": HELP_NOTES,
            "legends": HELP_LEGENDS,
            "workflows": [
                {
                    "task": "After editing an OpenCL kernel",
                    "command": "houdini-cli opencl sync <node-path>",
                },
                {
                    "task": "Inspect explicit node wiring",
                    "command": "houdini-cli node connections <node-path>",
                },
                {
                    "task": "Capture a viewport screenshot",
                    "command": "houdini-cli session screenshot --pane-name <pane>",
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
