"""CLI entrypoint and parser registration."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .commands import eval as eval_command
from .commands import node
from .commands import parm
from .commands import session
from .format.envelopes import error_result
from .runtime.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="houdini-cli",
        description="Agent-oriented CLI for controlling a live Houdini session.",
    )
    parser.add_argument("--host", default="localhost", help="Houdini host (default: localhost)")
    parser.add_argument("--port", type=int, default=18811, help="Houdini port (default: 18811)")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging on stderr.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    session.register_parser(subparsers)
    eval_command.register_parser(subparsers)
    parm.register_parser(subparsers)
    node.register_parser(subparsers)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(debug=args.debug)

    try:
        result = args.handler(args)
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")
        return 0 if result.get("ok", False) else 1
    except Exception as exc:  # pragma: no cover - top-level safety net
        json.dump(error_result(exc), sys.stdout)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
