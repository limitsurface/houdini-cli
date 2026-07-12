"""Structured help for the `python` command."""

PYTHON_TOPIC = {
    "description": "Inspect, validate, and safely synchronize Python COP #bind interfaces.",
    "notes": ["Python COP support is implemented first; SOP and LOP Python nodes are not yet supported.", "Sync preserves compatible spare values, expressions, custom folder placement, and input wires by name."],
    "children": {
        "inspect": {"description": "Inspect desired/current Python COP signatures, bindings, and controls.", "usage": "houdini-cli python inspect <node-path> [--details]"},
        "validate": {"description": "Validate a Python COP against #bind directives.", "usage": "houdini-cli python validate <node-path> [--details]"},
        "sync": {"description": "Safely synchronize Python COP ports, binding rows, and controls.", "usage": "houdini-cli python sync <node-path> [--dry-run] [--bindings-only] [--prune-generated] [--no-preserve-values] [--details]"},
    },
}
