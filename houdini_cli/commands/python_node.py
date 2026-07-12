"""Python node inspection and synchronization commands."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result
from ..transport.rpyc import connect
from .node_common import get_node
from .python_cop import extract_bindings, require_python_cop, sync, validation


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("python", help="Inspect and synchronize Python nodes.")
    commands = parser.add_subparsers(dest="python_command", required=True)
    for name, handler, help_text in (
        ("inspect", handle_inspect, "Inspect Python COP #bind interfaces and controls."),
        ("validate", handle_validate, "Validate a Python COP interface against its #bind directives."),
    ):
        child = commands.add_parser(name, help=help_text)
        child.add_argument("node_path")
        child.add_argument("--details", action="store_true")
        child.set_defaults(handler=handler)
    sync_parser = commands.add_parser("sync", help="Safely synchronize a Python COP from #bind directives.")
    sync_parser.add_argument("node_path")
    sync_parser.add_argument("--dry-run", action="store_true")
    sync_parser.add_argument("--bindings-only", action="store_true")
    sync_parser.add_argument("--prune-generated", action="store_true")
    sync_parser.add_argument("--preserve-values", action=argparse.BooleanOptionalAction, default=True)
    sync_parser.add_argument("--details", action="store_true")
    sync_parser.set_defaults(handler=handle_sync)


def _compact(data: dict) -> dict:
    result = {
        "node_path": data["node_path"], "context": data["context"], "binding_count": data["binding_count"],
        "clean": data["ok"], "sync_required": data["sync_required"],
        "input_count": len(data["current_inputs"]), "output_count": len(data["current_outputs"]),
        "control_count": len(data["controls"]), "missing_control_count": len(data["missing_controls"]),
        "unlinked_control_count": len(data["unlinked_controls"]),
        "stale_generated_count": len(data["stale_generated_controls"]),
    }
    if data["hints"]:
        result["hints"] = data["hints"]
    return result


def _read(node_path: str, host: str, port: int) -> tuple[dict, list]:
    with connect(host, port) as session:
        node = get_node(session, node_path)
        require_python_cop(node)
        bindings = extract_bindings(session, node)
        return validation(node, bindings), bindings


def handle_inspect(args: argparse.Namespace) -> dict:
    data, _bindings = _read(args.node_path, args.host, args.port)
    return success_result(data if args.details else _compact(data))


def handle_validate(args: argparse.Namespace) -> dict:
    data, _bindings = _read(args.node_path, args.host, args.port)
    return success_result(data if args.details else _compact(data))


def handle_sync(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        require_python_cop(node)
        bindings = extract_bindings(session, node)
        before = validation(node, bindings)
        if args.dry_run:
            result = {**_compact(before), "dry_run": True}
            if args.details:
                result["validation"] = before
            return success_result(result)
        changes = sync(session, node, bindings, bindings_only=args.bindings_only, prune_generated=args.prune_generated, preserve_values=args.preserve_values)
        after = validation(node, bindings)
        result = {**_compact(after), "dry_run": False, "bindings_only": args.bindings_only, "prune_generated": args.prune_generated, "preserve_values": args.preserve_values, **changes}
        if args.details:
            result["validation"] = after
        return success_result(result)
