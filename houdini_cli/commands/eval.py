"""Eval command."""

from __future__ import annotations

import argparse
import contextlib
import io

from ..format.envelopes import success_result
from ..transport.rpyc import connect


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("eval", help="Execute Python against the live Houdini session.")
    parser.add_argument("--code", required=True, help="Python code to execute.")
    parser.set_defaults(handler=handle_eval)


def handle_eval(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        exec_globals = {"hou": session.hou, "__builtins__": __builtins__}

        with (
            contextlib.redirect_stdout(stdout_capture),
            contextlib.redirect_stderr(stderr_capture),
        ):
            exec(args.code, exec_globals)

        return success_result(
            {
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
            }
        )
