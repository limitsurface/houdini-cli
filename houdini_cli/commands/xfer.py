"""Filesystem-backed node data transfer commands."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from typing import Any

from ..format.envelopes import success_result
from ..remote.xfer import XFER_REMOTE
from ..runtime.timeouts import XFER_TIMEOUT_SECONDS
from ..transport.rpyc import connect, localize


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("xfer", help="Transfer Houdini node data through disk artifacts.")
    commands = parser.add_subparsers(dest="xfer_command", required=True)

    export_parser = commands.add_parser("export", help="Export node data to disk.")
    export_parser.add_argument("node_path", help="Houdini node path to export.")
    export_parser.add_argument("--output", required=True, help="Destination JSON artifact path.")
    _add_capture_options(export_parser)
    export_parser.add_argument("--overwrite", action="store_true", help="Replace an existing artifact.")
    export_parser.set_defaults(handler=handle_export)

    import_parser = commands.add_parser("import", help="Recreate node data from disk.")
    import_parser.add_argument("artifact", help="JSON artifact path.")
    import_parser.add_argument("--to-parent", required=True, help="Destination parent network path.")
    import_parser.add_argument("--name", help="Destination root node name.")
    import_parser.add_argument("--unique", action="store_true", help="Allow a unique suffix on name conflicts.")
    import_parser.set_defaults(handler=handle_import)

    copy_parser = commands.add_parser("copy", help="Recreate a node between live Houdini sessions.")
    copy_parser.add_argument("node_path", help="Source Houdini node path.")
    copy_parser.add_argument("--to-parent", required=True, help="Destination parent network path.")
    copy_parser.add_argument("--from-host", help="Source Houdini host.")
    copy_parser.add_argument("--from-port", type=int, help="Source Houdini port.")
    copy_parser.add_argument("--to-host", help="Destination Houdini host.")
    copy_parser.add_argument("--to-port", type=int, help="Destination Houdini port.")
    copy_parser.add_argument("--name", help="Destination root node name.")
    copy_parser.add_argument("--unique", action="store_true", help="Allow a unique suffix on name conflicts.")
    _add_capture_options(copy_parser)
    copy_parser.set_defaults(handler=handle_copy)


def _add_capture_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--children", action="store_true", help="Capture recursive child contents.")
    parser.add_argument("--all-parms", action="store_true", help="Include default-valued parameters.")
    parser.add_argument("--editables", action="store_true", help="Capture editable asset contents.")


def _artifact_path(path: str) -> str:
    if path == "-":
        raise ValueError("Artifact paths cannot use stdin or stdout")
    return str(Path(path).expanduser().resolve())


def _remote_result(value: Any, operation: str) -> dict[str, Any]:
    result = localize(value)
    if not isinstance(result, dict):
        raise RuntimeError(f"Houdini returned invalid {operation} status")
    if not result.get("ok"):
        message = str(result.get("error") or f"Houdini {operation} failed")
        raise RuntimeError(message[:500])
    result.pop("ok", None)
    return result


def _export_to(
    host: str,
    port: int,
    node_path: str,
    output_path: str,
    *,
    children: bool,
    all_parms: bool,
    editables: bool,
    overwrite: bool,
) -> dict[str, Any]:
    with connect(host, port, sync_request_timeout_seconds=XFER_TIMEOUT_SECONDS) as session:
        result = _remote_result(
            XFER_REMOTE.evaluate(
                session.connection,
                "export",
                node_path,
                output_path,
                children,
                all_parms,
                editables,
                overwrite,
            ),
            "export",
        )
    return result


def _import_from(
    host: str,
    port: int,
    artifact_path: str,
    parent_path: str,
    *,
    name: str | None,
    unique: bool,
) -> dict[str, Any]:
    with connect(host, port, sync_request_timeout_seconds=XFER_TIMEOUT_SECONDS) as session:
        result = _remote_result(
            XFER_REMOTE.evaluate(
                session.connection,
                "import",
                artifact_path,
                parent_path,
                name,
                unique,
            ),
            "import",
        )
    return result


def handle_export(args: argparse.Namespace) -> dict:
    output_path = _artifact_path(args.output)
    result = _export_to(
        args.host,
        args.port,
        args.node_path,
        output_path,
        children=args.children,
        all_parms=args.all_parms,
        editables=args.editables,
        overwrite=args.overwrite,
    )
    return success_result({"operation": "export", **result})


def handle_import(args: argparse.Namespace) -> dict:
    artifact_path = _artifact_path(args.artifact)
    result = _import_from(
        args.host,
        args.port,
        artifact_path,
        args.to_parent,
        name=args.name,
        unique=args.unique,
    )
    return success_result({"operation": "import", **result})


def handle_copy(args: argparse.Namespace) -> dict:
    source_host = args.from_host or args.host
    source_port = args.from_port if args.from_port is not None else args.port
    destination_host = args.to_host or args.host
    destination_port = args.to_port if args.to_port is not None else args.port
    if source_host != destination_host:
        raise ValueError("xfer copy requires source and destination to use the same host")

    with tempfile.TemporaryDirectory(prefix="houdini-cli-xfer-") as directory:
        artifact_path = os.path.join(directory, "transfer.json")
        exported = _export_to(
            source_host,
            source_port,
            args.node_path,
            artifact_path,
            children=args.children,
            all_parms=args.all_parms,
            editables=args.editables,
            overwrite=False,
        )
        imported = _import_from(
            destination_host,
            destination_port,
            artifact_path,
            args.to_parent,
            name=args.name,
            unique=args.unique,
        )

    return success_result(
        {
            "operation": "copy",
            "source": {
                "host": source_host,
                "port": source_port,
                "path": args.node_path,
                "houdini_version": exported["source"]["houdini_version"],
                "hip_file": exported["source"]["hip_file"],
            },
            "destination": {
                "host": destination_host,
                "port": destination_port,
                "path": imported["path"],
                "houdini_version": imported["destination_houdini_version"],
                "hip_file": imported["destination_hip_file"],
            },
            "capture": exported["capture"],
            "source_summary": exported["summary"],
            "destination_summary": imported["destination_summary"],
            "verified": imported["verified"],
            "error_count": imported["error_count"],
            "warning_count": imported["warning_count"],
            "elapsed_seconds": exported["elapsed_seconds"] + imported["elapsed_seconds"],
        }
    )
