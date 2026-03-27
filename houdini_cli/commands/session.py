"""Session-oriented commands."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("ping", help="Verify Houdini connectivity.")
    parser.set_defaults(handler=handle_ping)


def handle_ping(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        return success_result(
            {
                "host": args.host,
                "port": args.port,
                "houdini_version": localize(session.hou.applicationVersionString()),
                "hip_file": localize(session.hou.hipFile.path()),
            }
        )
