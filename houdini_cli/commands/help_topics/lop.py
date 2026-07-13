"""Structured help for the `lop` command."""

LOP_TOPIC = {
    "description": "Inspect composed Solaris/USD stages with bounded summary-first reads.",
    "children": {
        "info": {
            "description": "Summarize the composed USD stage at one LOP output.",
            "usage": "houdini-cli lop info <node-path> [--output INDEX] [--max-depth N] "
            "[--max-prims N] [--top-types N] [--include-paths]",
            "notes": [
                "stage acquisition may cook; cook counts and timings are reported",
                "default output returns aggregate counts and never expands instance proxies",
                "--include-paths adds independently capped path lists",
            ],
        }
    },
}
