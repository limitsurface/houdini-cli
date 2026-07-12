"""VEX wrangle commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.input import read_text_input
from .node_common import get_node, node_summary

_RUN_OVER_CHOICES = ("detail", "primitive", "point", "vertex", "number")
_GROUP_TYPE_CHOICES = ("guess", "point", "primitive", "vertex")
_WRANGLE_KINDS = {
    "sop": ("Sop", "attribwrangle"),
    "lop": ("Lop", "attribwrangle"),
    "dop-geometry": ("Dop", "geometrywrangle"),
    "dop-pop": ("Dop", "popwrangle"),
    "dop-gas-field": ("Dop", "gasfieldwrangle"),
}
_SUPPORTED_WRANGLES = {(category, node_type) for category, node_type in _WRANGLE_KINDS.values()}


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("wrangle", help="Create and configure VEX wrangles.")
    wrangle_subparsers = parser.add_subparsers(dest="wrangle_command", required=True)

    create_parser = wrangle_subparsers.add_parser("create", help="Create a SOP, LOP, or DOP VEX wrangle.")
    create_parser.add_argument("parent_path", help="Parent network path.")
    create_parser.add_argument(
        "--kind",
        choices=tuple(_WRANGLE_KINDS),
        default="sop",
        help="Wrangle kind (default: sop).",
    )
    create_parser.add_argument("--name", help="Optional node name.")
    create_parser.add_argument("--group", default="", help="Optional element group.")
    create_parser.add_argument(
        "--group-type",
        choices=_GROUP_TYPE_CHOICES,
        default="guess",
        help="Group element type (default: guess).",
    )
    create_parser.add_argument(
        "--run-over",
        choices=_RUN_OVER_CHOICES,
        default="point",
        help="Wrangle execution class (default: point).",
    )
    source = create_parser.add_mutually_exclusive_group()
    source.add_argument("--vex", help="Inline VEX snippet, or '-' to read from stdin.")
    source.add_argument("--input", help="UTF-8 VEX file path or '-' to read from stdin.")
    create_parser.add_argument(
        "--create-spare-parms",
        action="store_true",
        help="Create spare parameters from channel calls after setting the snippet.",
    )
    create_parser.set_defaults(handler=handle_create)

    spare_parser = wrangle_subparsers.add_parser("spare-parms", help="Manage generated wrangle spare parameters.")
    spare_subparsers = spare_parser.add_subparsers(dest="wrangle_spare_parms_command", required=True)

    sync_parser = spare_subparsers.add_parser(
        "sync",
        help="Create spare parameters from channel calls in a wrangle snippet.",
    )
    sync_parser.add_argument("node_path", help="VEX wrangle node path.")
    sync_parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete all existing spare parameters before recreating them.",
    )
    sync_parser.set_defaults(handler=handle_spare_parms_sync)

    clear_parser = spare_subparsers.add_parser("clear", help="Delete all spare parameters from a wrangle.")
    clear_parser.add_argument("node_path", help="VEX wrangle node path.")
    clear_parser.set_defaults(handler=handle_spare_parms_clear)


def _snippet_source(args: argparse.Namespace) -> str | None:
    if args.vex is not None:
        if args.vex == "-":
            return read_text_input("-")
        return args.vex
    if args.input is not None:
        return read_text_input(args.input)
    return None


def _snippet_parm(node: Any) -> Any:
    node_type = node.type()
    identity = (localize(node_type.category().name()), localize(node_type.name()))
    snippet = node.parm("snippet")
    if identity not in _SUPPORTED_WRANGLES or snippet is None:
        raise ValueError(f"Node is not a supported VEX wrangle: {localize(node.path())}")
    return snippet


def _sop_wrangle_parms(node: Any) -> tuple[Any, Any, Any]:
    group = node.parm("group")
    run_over = node.parm("class")
    snippet = _snippet_parm(node)
    if group is None or run_over is None or snippet is None:
        raise ValueError(f"Node is not a supported VEX wrangle: {localize(node.path())}")
    return group, run_over, snippet


def _spare_parm_names(node: Any) -> list[str]:
    return [
        localize(parm.name())
        for parm in node.spareParms()
        if localize(parm.parmTemplate().type().name()) not in {"Folder", "FolderSet"}
    ]


def _create_spare_parms(session: Any, node: Any, *, clear: bool) -> dict[str, Any]:
    _snippet_parm(node)
    before = _spare_parm_names(node)
    if clear:
        node.removeSpareParms()
    session.connection.modules.vexpressionmenu.createSpareParmsFromChCalls(node, "snippet")
    after = _spare_parm_names(node)
    return {
        "cleared": clear,
        "before": before,
        "after": after,
        "created": [name for name in after if name not in before or clear],
    }


def handle_create(args: argparse.Namespace) -> dict:
    snippet_text = _snippet_source(args)
    if args.create_spare_parms and snippet_text is None:
        raise ValueError("--create-spare-parms requires --vex or --input")

    with connect(args.host, args.port) as session:
        parent = get_node(session, args.parent_path)
        expected_category, node_type = _WRANGLE_KINDS[args.kind]
        actual_category = localize(parent.childTypeCategory().name())
        if actual_category != expected_category:
            raise ValueError(
                f"Wrangle kind {args.kind!r} requires a {expected_category} network; "
                f"{localize(parent.path())} contains {actual_category} nodes"
            )
        node = parent.createNode(node_type, args.name) if args.name else parent.createNode(node_type)
        snippet = _snippet_parm(node)
        sop_details: dict[str, Any] = {}
        if args.kind == "sop":
            group, run_over, snippet = _sop_wrangle_parms(node)
            group.set(args.group)
            node.parm("grouptype").set(args.group_type)
            run_over.set(args.run_over)
            sop_details = {
                "group": args.group,
                "group_type": args.group_type,
                "run_over": args.run_over,
            }
        if snippet_text is not None:
            snippet.set(snippet_text)

        spare_parms = None
        if args.create_spare_parms:
            spare_parms = _create_spare_parms(session, node, clear=False)

        return success_result(
            {
                **node_summary(node),
                "kind": args.kind,
                **sop_details,
                "snippet_set": snippet_text is not None,
                "spare_parms": spare_parms,
            }
        )


def handle_spare_parms_sync(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        return success_result(
            {
                "node_path": localize(node.path()),
                **_create_spare_parms(session, node, clear=args.clear),
            }
        )


def handle_spare_parms_clear(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        _snippet_parm(node)
        removed = _spare_parm_names(node)
        node.removeSpareParms()
        return success_result(
            {
                "node_path": localize(node.path()),
                "removed": removed,
            }
        )
