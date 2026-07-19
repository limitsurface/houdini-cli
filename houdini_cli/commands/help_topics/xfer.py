"""Structured help for the `xfer` command."""

XFER_TOPIC = {
    "description": "Transfer Houdini node data through filesystem-backed artifacts.",
    "notes": [
        "network payloads are written to disk and never returned over RPyC",
        "use node summary, find, neighbors, and focused reads for ordinary inspection",
    ],
    "children": {
        "export": {
            "description": "Export node data to a JSON artifact on disk.",
            "usage": "houdini-cli xfer export <node-path> --output <file> "
            "[--children] [--all-parms] [--editables] [--overwrite]",
            "notes": [
                "use broad exports only for explicit transfer or exceptional offline inspection",
                "--children recurses into subnets and unlocked assets; --editables includes editable asset contents",
                "--all-parms includes default-valued parameters",
            ],
        },
        "import": {
            "description": "Recreate node data from a JSON artifact on disk.",
            "usage": "houdini-cli xfer import <file> --to-parent <network-path> "
            "[--name <node-name>] [--unique]",
            "notes": ["existing destination names fail unless --unique is used"],
        },
        "copy": {
            "description": "Recreate a node between live Houdini sessions.",
            "usage": "houdini-cli xfer copy <node-path> --to-parent <network-path> "
            "[--from-host <host>] [--from-port <port>] "
            "[--to-host <host>] [--to-port <port>] "
            "[--name <node-name>] [--unique] [--children] "
            "[--all-parms] [--editables]",
            "notes": [
                "requires source and destination sessions to share filesystem access",
                "returns bounded transfer status without returning network contents",
            ],
        },
    },
}
