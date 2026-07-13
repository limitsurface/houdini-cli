"""Solaris/USD stage inspection commands."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result
from ..remote.lop_stage import LOP_STAGE_REMOTE
from ..runtime.timeouts import BROAD_READ_TIMEOUT_SECONDS
from ..transport.rpyc import connect, localize, sync_request_timeout

DEFAULT_MAX_PRIMS = 10000
DEFAULT_TOP_TYPES = 20
DEFAULT_PATH_LIMIT = 50


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    lop_parser = subparsers.add_parser("lop", help="Inspect composed Solaris/USD stages.")
    lop_subparsers = lop_parser.add_subparsers(dest="lop_command", required=True)

    info_parser = lop_subparsers.add_parser("info", help="Summarize a composed USD stage.")
    info_parser.add_argument("node_path", help="LOP node path.")
    info_parser.add_argument("--output", type=int, default=0, help="LOP output index (default: 0).")
    info_parser.add_argument("--max-depth", type=int, help="Maximum USD prim depth below the pseudo-root.")
    info_parser.add_argument(
        "--max-prims",
        type=int,
        default=DEFAULT_MAX_PRIMS,
        help=f"Maximum prims to visit (default: {DEFAULT_MAX_PRIMS}).",
    )
    info_parser.add_argument(
        "--top-types",
        type=int,
        default=DEFAULT_TOP_TYPES,
        help=f"Maximum prim type histogram rows (default: {DEFAULT_TOP_TYPES}).",
    )
    info_parser.add_argument("--include-paths", action="store_true", help="Include independently bounded useful prim path lists.")
    info_parser.set_defaults(handler=handle_info)


def _validate_args(args: argparse.Namespace) -> None:
    if args.output < 0:
        raise ValueError(f"Output index must not be negative: {args.output}")
    if args.max_depth is not None and args.max_depth < 0:
        raise ValueError(f"Maximum depth must not be negative: {args.max_depth}")
    if args.max_prims <= 0:
        raise ValueError(f"Maximum prims must be positive: {args.max_prims}")
    if args.top_types <= 0:
        raise ValueError(f"Top types must be positive: {args.top_types}")


def handle_info(args: argparse.Namespace) -> dict:
    _validate_args(args)
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, BROAD_READ_TIMEOUT_SECONDS):
            data = localize(
                LOP_STAGE_REMOTE.evaluate(
                    session.connection,
                    "summary",
                    args.node_path,
                    args.output,
                    args.max_depth,
                    args.max_prims,
                    args.top_types,
                    args.include_paths,
                    DEFAULT_PATH_LIMIT,
                )
            )
    return success_result(data)
