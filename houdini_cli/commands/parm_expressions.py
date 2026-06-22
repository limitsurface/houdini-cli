"""Parameter expression commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.input import read_text_input
from .parm_common import get_parm


def expression_language(session: Any, name: str) -> Any:
    return session.hou.exprLanguage.Python if name == "python" else session.hou.exprLanguage.Hscript


def handle_expression_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = get_parm(session, args.parm_path)
        try:
            expression = localize(parm.expression())
            language = localize(parm.expressionLanguage().name()).lower()
        except Exception:
            expression = None
            language = None
        return success_result(
            {
                "parm_path": args.parm_path,
                "has_expression": expression is not None,
                "expression": expression,
                "language": language,
            }
        )


def handle_expression_set(args: argparse.Namespace) -> dict:
    if bool(args.text is not None) == bool(args.input is not None):
        raise ValueError("Provide exactly one of --text or --input")
    text = args.text if args.text is not None else read_text_input(args.input)
    with connect(args.host, args.port) as session:
        parm = get_parm(session, args.parm_path)
        parm.setExpression(text, expression_language(session, args.language))
        return success_result(
            {
                "parm_path": args.parm_path,
                "expression": text,
                "language": args.language,
                "applied": True,
            }
        )


def handle_expression_clear(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = get_parm(session, args.parm_path)
        value = localize(parm.eval()) if args.keep_value else None
        parm.deleteAllKeyframes()
        if args.keep_value:
            parm.set(value)
        return success_result(
            {
                "parm_path": args.parm_path,
                "cleared": True,
                "kept_value": value if args.keep_value else None,
            }
        )


def is_string_parm(session: Any, parm: Any) -> bool:
    return parm.parmTemplate().type() == session.hou.parmTemplateType.String


def handle_reference(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        target = get_parm(session, args.target_parm)
        source = get_parm(session, args.source_parm)
        function = "chs" if is_string_parm(session, source) else "ch"
        if args.absolute:
            referenced_path = localize(source.path())
        else:
            node_path = localize(target.node().relativePathTo(source.node()))
            referenced_path = f"{node_path}/{localize(source.name())}" if node_path != "." else localize(source.name())
        expression = f'{function}("{referenced_path}")'
        target.setExpression(expression, session.hou.exprLanguage.Hscript)
        return success_result(
            {
                "target_parm": args.target_parm,
                "source_parm": args.source_parm,
                "relative": not args.absolute,
                "expression": expression,
                "applied": True,
            }
        )
