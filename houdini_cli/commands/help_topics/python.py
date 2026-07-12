"""Structured help for the `python` command."""

PYTHON_TOPIC = {
    "description": "Inspect, validate, and safely synchronize Python COP and Python Snippet SOP #bind interfaces.",
    "notes": ["Classic Python SOPs and LOP Python Script nodes do not use this #bind workflow and are not supported.", "Sync preserves compatible spare values, expressions, and custom folder placement; COP input wires are restored by name."],
    "children": {
        "inspect": {"description": "Inspect desired/current Python COP or Python Snippet SOP bindings and controls.", "usage": "houdini-cli python inspect <node-path> [--details]"},
        "validate": {"description": "Validate a supported Python node against #bind directives.", "usage": "houdini-cli python validate <node-path> [--details]"},
        "sync": {"description": "Safely synchronize supported Python-node binding rows and controls, plus COP ports.", "usage": "houdini-cli python sync <node-path> [--dry-run] [--bindings-only] [--prune-generated] [--no-preserve-values] [--details]"},
    },
}
