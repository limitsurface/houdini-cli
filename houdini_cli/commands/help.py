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
    "wrangle": {
        "description": "Create Attribute Wrangles and synchronize spare parameters from VEX channel calls.",
        "notes": [
            "Spare parameter creation delegates to Houdini's native VEX expression helper.",
            "wrangle spare-parms sync preserves compatible existing spare parameters unless --clear is used.",
        ],
        "children": {
            "create": {
                "description": "Create and configure an Attribute Wrangle SOP.",
                "usage": "houdini-cli wrangle create <parent-path> [--name NAME] [--group GROUP] [--group-type TYPE] [--run-over CLASS] [--vex CODE | --input PATH] [--create-spare-parms]",
            },
            "spare-parms": {
                "description": "Synchronize or clear wrangle spare parameters.",
                "children": {
                    "sync": {
                        "description": "Create spare parameters from channel calls in the VEX snippet.",
                        "usage": "houdini-cli wrangle spare-parms sync <node-path> [--clear]",
                    },
                    "clear": {
                        "description": "Delete all spare parameters from a wrangle.",
                        "usage": "houdini-cli wrangle spare-parms clear <node-path>",
                    },
                },
            },
        },
    },
    "session": {
        "description": "Inspect or control session-level state such as connectivity, frame, viewport screenshots, and viewport camera state.",
        "children": {
            "ping": {
                "description": "Verify that Houdini is reachable over hrpyc/rpyc.",
                "usage": "houdini-cli session ping",
                "examples": ["uv run houdini-cli session ping"],
            },
            "save": {
                "description": "Save the current Houdini scene to its existing HIP path.",
                "usage": "houdini-cli session save",
            },
            "save-as": {
                "description": "Save the current Houdini scene to a new HIP path.",
                "usage": "houdini-cli session save-as <path> [--force]",
                "notes": [
                    "Houdini variables in the path are expanded",
                    "existing destinations require --force",
                    "missing parent directories are created",
                ],
            },
            "frame": {
                "description": "Read or set the current timeline frame.",
                "usage": "houdini-cli session frame [<frame>]",
                "examples": [
                    "uv run houdini-cli session frame",
                    "uv run houdini-cli session frame 24",
                ],
            },
            "selection": {
                "description": "Read the currently selected node paths from the Houdini UI.",
                "usage": "houdini-cli session selection [--include-hidden]",
                "notes": [
                    "the last path in `paths` is also returned as `current` and matches Houdini's global current node",
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
            "viewport": {
                "description": "Read or manipulate the active viewport in a Scene Viewer pane.",
                "children": {
                    "get": {
                        "description": "Read viewport type and current free-camera state.",
                        "usage": "houdini-cli session viewport get [--pane-name <name> | --index <n>]",
                    },
                    "focus-selected": {
                        "description": "Frame the current Scene Viewer selection, like Space+F in the viewport.",
                        "usage": "houdini-cli session viewport focus-selected [--pane-name <name> | --index <n>]",
                        "notes": [
                            "requires graphical Houdini UI and an active Scene Viewer selection",
                        ],
                    },
                    "axis": {
                        "description": "Switch the viewport to a fixed axis view or perspective.",
                        "usage": "houdini-cli session viewport axis <+x|-x|+y|-y|+z|-z|persp> [--pane-name <name> | --index <n>]",
                        "notes": [
                            "+x/-x map to right/left, +y/-y map to top/bottom, +z/-z map to front/back",
                        ],
                    },
                    "set": {
                        "description": "Set the perspective viewport camera translation, rotation, and optional pivot.",
                        "usage": "houdini-cli session viewport set [--pane-name <name> | --index <n>] [--t X Y Z] [--r RX RY RZ] [--pivot X Y Z]",
                        "notes": [
                            "only supports perspective views; switch with `session viewport axis persp` if needed",
                        ],
                    },
                },
            },
        }
    },
    "shelf": {
        "description": "Inspect shelves, search shelf tools, and create or edit tool scripts.",
        "children": {
            "list": {
                "description": "List known shelves in a compact row format.",
                "usage": "houdini-cli shelf list",
            },
            "tools": {
                "description": "List tools on one shelf in a compact row format.",
                "usage": "houdini-cli shelf tools <shelf-name>",
            },
            "find": {
                "description": "Search shelves and shelf tools by case-insensitive text.",
                "usage": "houdini-cli shelf find --query <text>",
            },
            "tool": {
                "description": "Create, edit, or delete shelf tools.",
                "children": {
                    "add": {
                        "description": "Add a new Python shelf tool to one shelf from stdin or a file.",
                        "usage": "houdini-cli shelf tool add <shelf-name> <tool-name> --label <label> --input <path-or-'-'>",
                    },
                    "edit": {
                        "description": "Edit an existing shelf tool label or script and optionally attach it to a shelf.",
                        "usage": "houdini-cli shelf tool edit <tool-name> [--label <label>] [--shelf <shelf-name>] [--input <path-or-'-'>]",
                    },
                    "delete": {
                        "description": "Delete a tool from one shelf or all shelves and destroy it if unused.",
                        "usage": "houdini-cli shelf tool delete <tool-name> [--shelf <shelf-name>]",
                    },
                },
            },
        },
    },
    "eval": {
        "description": "Execute Python against the live Houdini session when no structured command fits.",
        "usage": "houdini-cli eval (--code <python> | --input <path-or-'-'>)",
        "examples": [
            'uv run houdini-cli eval --code "print(hou.applicationVersionString())"',
            "Get-Content script.py -Raw | uv run houdini-cli eval --input -",
            "cat script.py | houdini-cli eval --input -",
        ],
        "notes": [
            "--code and --input are mutually exclusive",
            "--input reads UTF-8 files or stdin when set to -",
        ],
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
            "expression": {
                "description": "Inspect, set, or clear parameter expressions.",
                "children": {
                    "get": {
                        "description": "Read a parameter expression and language.",
                        "usage": "houdini-cli parm expression get <parm-path>",
                    },
                    "set": {
                        "description": "Set a parameter expression from an argument, file, or stdin.",
                        "usage": "houdini-cli parm expression set <parm-path> [--language hscript|python] (--text TEXT | --input <path-or-'-'>)",
                    },
                    "clear": {
                        "description": "Clear expressions/keyframes and optionally preserve the evaluated value.",
                        "usage": "houdini-cli parm expression clear <parm-path> [--keep-value]",
                    },
                },
            },
            "reference": {
                "description": "Create a typed HScript reference from one parameter to another.",
                "usage": "houdini-cli parm reference <target-parm> <source-parm> [--relative|--absolute]",
                "notes": [
                    "uses chs() for string parameters and ch() for numeric parameters",
                    "relative references are the default",
                ],
            },
            "find": {
                "description": "Search parameter names, raw values, expressions, and resolved references on one node.",
                "usage": "houdini-cli parm find <node-path> --query TEXT [--raw] [--expressions] [--resolved-targets] [--max-matches N]",
                "notes": [
                    "query matching checks names, paths, raw values, expressions, and resolved targets",
                    "detail flags control which extra fields are returned in matching rows",
                ],
            },
            "refs": {
                "description": "List resolved parameter references on one node.",
                "usage": "houdini-cli parm refs <node-path> [--external-to ROOT] [--max-refs N]",
                "notes": [
                    "--external-to marks references outside the supplied node or network root",
                ],
            },
            "template": {
                "description": "Inspect or patch parameter-template UI and default metadata.",
                "children": {
                    "get": {
                        "description": "Read a focused parameter-template summary.",
                        "usage": "houdini-cli parm template get <parm-path> [--target instance|definition]",
                    },
                    "set": {
                        "description": "Apply a partial parameter-template patch from JSON.",
                        "usage": "houdini-cli parm template set <parm-path> [--target instance|definition] --input <path-or-'-'>",
                        "notes": [
                            "supports label, help, tags, default, numeric ranges, strictness, join-with-next, and conversion to a named menu",
                            "definition targeting updates and saves the owning HDA definition",
                        ],
                    },
                },
            },
            "default": {
                "description": "Modify parameter-template defaults.",
                "children": {
                    "set": {
                        "description": "Set a template default from the current value or JSON.",
                        "usage": "houdini-cli parm default set <parm-path> [--target instance|definition] (--current | --value JSON)",
                    },
                },
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
                "description": "Create a node or tool recipe under a parent network.",
                "usage": "houdini-cli node create <parent-path> <node-or-recipe-key> [--name <node-name>]",
                "notes": ["tool recipes may create multiple nodes; --name applies only to ordinary nodes"],
            },
            "rename": {
                "description": "Rename one node and return its old and new paths.",
                "usage": "houdini-cli node rename <node-path> <new-name> [--unique]",
            },
            "copy": {
                "description": "Copy one or more nodes to another parent while preserving internal wiring.",
                "usage": "houdini-cli node copy <node-path> [<node-path> ...] --parent <network-path>",
                "notes": [
                    "all source nodes must share one parent network",
                    "returns an old-path to new-path map",
                ],
            },
            "move": {
                "description": "Move one or more nodes to another parent while preserving internal wiring.",
                "usage": "houdini-cli node move <node-path> [<node-path> ...] --parent <network-path>",
                "notes": [
                    "all source nodes must share one parent network",
                    "this reparents nodes; it does not change Network Editor positions",
                ],
            },
            "delete": {
                "description": "Delete a node.",
                "usage": "houdini-cli node delete <node-path>",
            },
            "get": {
                "description": "Read a focused node summary or a structured node section.",
                "usage": "houdini-cli node get <node-path> [--section parms|inputs|references|full] [--external-only]",
                "examples": ["uv run houdini-cli node get /obj/cli_attrib_live/OUT --section inputs"],
                "notes": [
                    "references reports parameter dependency targets and explicit input connections",
                    "--external-only applies to the references section and filters dependencies outside the inspected root",
                ],
            },
            "errors": {
                "description": "Read errors, warnings, and messages from one or more nodes.",
                "usage": "houdini-cli node errors <node-path> [<node-path> ...] [--cook]",
                "notes": ["By default this reads existing messages without cooking the nodes."],
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
                    "For --section inputs, pass a JSON array of connection rows with from/from_index/to_index fields.",
                    "Use named COP output/input ports when numeric indices are ambiguous.",
                ],
                "examples": [
                    'uv run houdini-cli node set /obj/copnet/opencl1 --section inputs --json "[{\\"from\\":\\"/obj/copnet/src\\",\\"from_index\\":\\"output1\\",\\"to_index\\":\\"input1\\"}]"',
                    'Get-Content inputs.json | uv run houdini-cli node set /obj/copnet/opencl1 --section inputs --json -',
                    'uv run houdini-cli node set /obj/copnet/merge1 --section inputs --json "[{\\"from\\":\\"/obj/copnet/A\\",\\"from_index\\":0,\\"to_index\\":0},{\\"from\\":\\"/obj/copnet/B\\",\\"from_index\\":0,\\"to_index\\":1}]"',
                ],
            },
            "flags": {
                "description": "Read or set focused display, render, bypass, and Compress flags.",
                "children": {
                    "get": {
                        "description": "Read focused node flags.",
                        "usage": "houdini-cli node flags get <node-path>",
                    },
                    "set": {
                        "description": "Set one or more focused node flags.",
                        "usage": "houdini-cli node flags set <node-path> [--display BOOL] [--render BOOL] [--bypass BOOL] [--compress BOOL]",
                        "notes": [
                            "Compress controls expanded or compact node presentation, including COP live previews",
                        ],
                    },
                },
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
    "hda": {
        "description": "Create, inspect, package, update, and validate Houdini digital assets.",
        "children": {
            "inspect": {
                "description": "Summarize an HDA instance, definition, interface, sections, tools, and library.",
                "usage": "houdini-cli hda inspect <asset-node> [--parms] [--sections] [--tools]",
            },
            "definitions": {
                "description": "List HDA definitions by library, category, namespace, or name.",
                "usage": "houdini-cli hda definitions [--library PATH] [--category CATEGORY] [--namespace NS] [--name TEXT] [--type-name TEXT] [--sections] [--max N|--all]",
                "notes": [
                    "broad scans are capped by default; use filters first in large sessions",
                    "--sections includes embedded section names and sizes, which is intentionally omitted by default",
                ],
            },
            "libraries": {
                "description": "List loaded HDA libraries and the definitions they provide.",
                "usage": "houdini-cli hda libraries [--library TEXT] [--definition TEXT] [--max N|--all]",
                "notes": [
                    "broad scans are capped by default; use filters first in large sessions",
                ],
            },
            "package": {
                "description": "Create, publish, and validate an HDA from an existing plain subnet.",
                "usage": "houdini-cli hda package <subnet-path> --type-name TYPE --label LABEL --library PATH [options]",
                "notes": ["the initial implementation packages existing subnets; explicit node lists and selection follow later"],
            },
            "create": {
                "description": "Convert an existing plain subnet into a digital asset.",
                "usage": "houdini-cli hda create <subnet-path> --type-name TYPE --label LABEL --library PATH [options]",
            },
            "update": {
                "description": "Update selected HDA definition surfaces from an editable instance.",
                "usage": "houdini-cli hda update <asset-node> [--contents] [--interface] [--sections] [--tools] [--all] [--validate]",
                "notes": ["without surface flags, contents is updated; --all uses contents -> interface -> sections -> tools -> save -> match -> validate"],
            },
            "save": {
                "description": "Save an HDA definition to its current or specified library.",
                "usage": "houdini-cli hda save <asset-node> [--library PATH]",
            },
            "instantiate": {
                "description": "Create a new instance of an installed HDA type.",
                "usage": "houdini-cli hda instantiate <type-name> --parent PATH [--name NAME] [--input NODE] [--expanded]",
            },
            "match": {
                "description": "Discard instance edits and match the current HDA definition.",
                "usage": "houdini-cli hda match <asset-node> [--force]",
            },
            "unlock": {
                "description": "Allow editing of an HDA instance's contents.",
                "usage": "houdini-cli hda unlock <asset-node> [--propagate]",
            },
            "install": {
                "description": "Install an HDA library into the current Houdini session.",
                "usage": "houdini-cli hda install <library> [--force]",
            },
            "uninstall": {
                "description": "Uninstall an HDA library from the current Houdini session.",
                "usage": "houdini-cli hda uninstall <library> --force",
            },
            "validate": {
                "description": "Validate definition state, fresh instantiation, cooking, and interface behavior.",
                "usage": "houdini-cli hda validate <asset-node> [--fresh-instance] [--cook] [--frames CSV] [--strict]",
            },
            "parms": {
                "description": "Inspect, apply, promote, and synchronize HDA parameters.",
                "children": {
                    "inspect": {
                        "description": "List published HDA parameters as compact flat rows with folder paths.",
                        "usage": "houdini-cli hda parms inspect <asset-node> [--folder PATH] [--name TEXT] [--values] [--defaults] [--tree]",
                    },
                    "find": {
                        "description": "Search published HDA parameter names and labels.",
                        "usage": "houdini-cli hda parms find <asset-node> --name TEXT [--values] [--defaults]",
                    },
                    "folders": {
                        "description": "List published HDA folders and child counts.",
                        "usage": "houdini-cli hda parms folders <asset-node>",
                    },
                    "locate": {
                        "description": "Locate one published HDA parameter and report its folder, value, and default.",
                        "usage": "houdini-cli hda parms locate <asset-node> <parm-name>",
                    },
                    "apply": {
                        "description": "Apply a declarative HDA parameter interface.",
                        "usage": "houdini-cli hda parms apply <asset-node> --input <path-or-'-'> [--replace-all]",
                        "notes": [
                            "supports nested tabs, simple/collapsible folders, headings, and separators",
                            "value parameters may define callback and callback_language (python or hscript)",
                            "supports float_ramp and color_ramp parameters",
                        ],
                    },
                    "promote": {"description": "Promote an internal parameter onto the HDA interface.", "usage": "houdini-cli hda parms promote <asset-node> <internal-parm> --name NAME [options]"},
                    "defaults": {"description": "Synchronize HDA defaults from current values.", "usage": "houdini-cli hda parms defaults <asset-node> --from-current"},
                },
            },
            "section": {
                "description": "List, read, write, or delete embedded HDA definition sections.",
                "children": {
                    "list": {"description": "List embedded section names and sizes.", "usage": "houdini-cli hda section list <asset-node>"},
                    "get": {"description": "Read an embedded section.", "usage": "houdini-cli hda section get <asset-node> <name> [--output PATH]"},
                    "set": {"description": "Create or replace an embedded section.", "usage": "houdini-cli hda section set <asset-node> <name> --input <path-or-'-'>"},
                    "delete": {"description": "Delete an embedded section.", "usage": "houdini-cli hda section delete <asset-node> <name> --force"},
                },
            },
            "script": {
                "description": "Manage common OnCreated, OnLoaded, OnUpdated, and PythonModule sections.",
                "children": {
                    "get": {"description": "Read a common HDA script section.", "usage": "houdini-cli hda script get <asset-node> <name>"},
                    "set": {"description": "Create or replace a common HDA script section.", "usage": "houdini-cli hda script set <asset-node> <name> --input <path-or-'-'>"},
                    "delete": {"description": "Delete a common HDA script section.", "usage": "houdini-cli hda script delete <asset-node> <name> --force"},
                },
            },
            "tool": {
                "description": "Inspect, create, or remove generated Tab-menu tool metadata.",
                "children": {
                    "inspect": {"description": "Inspect Tools.shelf metadata.", "usage": "houdini-cli hda tool inspect <asset-node>"},
                    "set": {"description": "Create or replace generated Tab-menu tool metadata.", "usage": "houdini-cli hda tool set <asset-node> --submenu PATH [--context CATEGORY] [--icon ICON]"},
                    "remove": {"description": "Remove generated Tab-menu tool metadata.", "usage": "houdini-cli hda tool remove <asset-node> --force"},
                },
            },
        },
    },
    "cop": {
        "description": "Inspect cooked Copernicus image/layer data.",
        "children": {
            "info": {
                "description": "Read cooked layer metadata for a COP node or selected output proxy node.",
                "usage": "houdini-cli cop info <node-path> [--output <index-or-name>]",
                "notes": [
                    "for output proxy nodes such as downstream nulls, the command infers the upstream producer output identity from the first input connection",
                ],
            },
            "sample": {
                "description": "Sample one or more pixel locations from a COP output.",
                "usage": "houdini-cli cop sample <node-path> [--output <index-or-name>] (--x X --y Y | --points <json-or-'-'>)",
            },
        }
    },
    "opencl": {
        "description": "Synchronize OpenCL node bindings and generated spare parameters across COP, SOP, and DOP contexts.",
        "notes": [
            "After editing an OpenCL kernel, run: houdini-cli opencl sync <node-path>",
            "Use opencl validate to check current port types, kernel/signature drift, and stale incompatible wires before or after syncing.",
            "Use --bindings-only when you want to refresh bindings/parms without changing the visible signature.",
        ],
        "children": {
            "validate": {
                "description": "Validate OpenCL COP signatures, SOP bindings, or DOP parameter rows against kernel #bind directives.",
                "usage": "houdini-cli opencl validate <node-path> [--details]",
                "examples": [
                    "uv run houdini-cli opencl validate /obj/geo1/work_here/opencl1",
                ],
            },
            "sync": {
                "description": "Refresh an OpenCL node from #bind directives using COP signatures, SOP bindings, or Gas OpenCL DOP parameters.",
                "usage": "houdini-cli opencl sync <node-path> [--clear] [--bindings-only] [--disconnect-invalid] [--details]",
                "examples": [
                    "uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1",
                    "uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1 --bindings-only",
                    "uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1 --clear",
                    "uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1 --disconnect-invalid",
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
            "summary": {
                "description": "List compact grouped attribute definitions.",
                "usage": "houdini-cli attrib summary <node-path> [--class point|prim|vertex|detail] [--max-attribs N]",
            },
            "geom-summary": {
                "description": "Summarize cooked geometry element counts.",
                "usage": "houdini-cli attrib geom-summary <node-path> [--topology] [--max-prims N] [--max-histogram N]",
                "notes": [
                    "default output avoids primitive scans and returns only point, primitive, and vertex counts",
                    "--topology adds primitive type and vertex-count histograms, capped by --max-prims",
                ],
            },
            "get": {
                "description": "Read attribute metadata and sampled values.",
                "usage": "houdini-cli attrib get <node-path> <attrib-name> --class point|prim|vertex|detail [--element N] [--limit N]",
            },
        }
    },
    "nodetype": {
        "description": "Discover creatable node types and tool recipes by category, query, or prefix.",
        "notes": [
            "results use kind=node or kind=recipe; only tool recipes appear because decorations and presets apply to existing targets",
        ],
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
    "recipe": {
        "description": "Discover, apply, and create Houdini recipes.",
        "notes": [
            "tool recipes create networks; decorations target existing nodes; node and parm presets target existing values",
            "interactive placement and drop-on-wire are intentionally excluded",
        ],
        "children": {
            "list": {
                "description": "List recipes, optionally by category.",
                "usage": "houdini-cli recipe list [--category tool|decoration|node-preset|parm-preset] [--visible-only] [--limit N]",
            },
            "find": {
                "description": "Search recipe keys and labels.",
                "usage": "houdini-cli recipe find --query TEXT [--category CATEGORY] [--visible-only] [--limit N]",
            },
            "get": {
                "description": "Inspect recipe metadata and stored payload.",
                "usage": "houdini-cli recipe get <recipe-key>",
            },
            "apply": {
                "description": "Apply a category-specific recipe.",
                "usage": "houdini-cli recipe apply <tool|decoration|node-preset|parm-preset> <recipe-key> <target-option>",
            },
            "create": {
                "description": "Create a category-specific recipe asset.",
                "usage": "houdini-cli recipe create <tool|decoration|node-preset|parm-preset> <recipe-key> [options]",
                "notes": ["requires --label and --library; existing keys require --force"],
            },
        },
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
