"""Eval command."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result
from ..runtime.timeouts import EVAL_TIMEOUT_SECONDS
from ..transport.rpyc import connect, localize, sync_request_timeout


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("eval", help="Execute Python against the live Houdini session.")
    parser.add_argument("--code", required=True, help="Python code to execute.")
    parser.set_defaults(handler=handle_eval)


def handle_eval(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        with sync_request_timeout(session, EVAL_TIMEOUT_SECONDS):
            namespace = session.connection.namespace
            namespace["_houdini_cli_eval_code"] = args.code
            session.connection.execute(
                """
import contextlib as _houdini_cli_contextlib
import io as _houdini_cli_io
import hou as _houdini_cli_hou

_houdini_cli_stdout = _houdini_cli_io.StringIO()
_houdini_cli_stderr = _houdini_cli_io.StringIO()
_houdini_cli_globals = {"hou": _houdini_cli_hou, "__builtins__": __builtins__}

with (
    _houdini_cli_contextlib.redirect_stdout(_houdini_cli_stdout),
    _houdini_cli_contextlib.redirect_stderr(_houdini_cli_stderr),
):
    exec(_houdini_cli_eval_code, _houdini_cli_globals)

_houdini_cli_eval_stdout = _houdini_cli_stdout.getvalue()
_houdini_cli_eval_stderr = _houdini_cli_stderr.getvalue()
"""
            )

            return success_result(
                {
                    "stdout": localize(namespace["_houdini_cli_eval_stdout"]),
                    "stderr": localize(namespace["_houdini_cli_eval_stderr"]),
                }
            )
