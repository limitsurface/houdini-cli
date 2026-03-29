"""Session-oriented commands."""

from __future__ import annotations

import argparse
import re

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize

_FCUR_FRAME_PATTERN = re.compile(r"Frame\s+(-?\d+(?:\.\d+)?)")


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ping_parser = subparsers.add_parser("ping", help="Verify Houdini connectivity.")
    ping_parser.set_defaults(handler=handle_ping)

    session_parser = subparsers.add_parser("session", help="Inspect or control the live Houdini session.")
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)

    session_ping_parser = session_subparsers.add_parser("ping", help="Verify Houdini connectivity.")
    session_ping_parser.set_defaults(handler=handle_ping)

    frame_parser = session_subparsers.add_parser(
        "frame",
        help="Get or set the current timeline frame.",
    )
    frame_parser.add_argument("frame", nargs="?", type=int, help="Optional frame to set before reporting.")
    frame_parser.set_defaults(handler=handle_frame)


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


def handle_frame(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        requested_frame = getattr(args, "frame", None)
        if requested_frame is not None:
            session.hou.hscript(f"fcur {requested_frame}")

        output, _ = session.hou.hscript("fcur")
        current_frame = _parse_fcur_frame(localize(output))

        return success_result(
            {
                "frame": current_frame,
            }
        )


def _parse_fcur_frame(output: str) -> int:
    match = _FCUR_FRAME_PATTERN.search(output)
    if not match:
        raise ValueError(f"Unexpected fcur output: {output!r}")
    return int(float(match.group(1)))
