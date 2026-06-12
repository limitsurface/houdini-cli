"""Recipe discovery, application, creation, and deletion commands."""

from __future__ import annotations

import argparse
import json
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.input import read_text_input
from .node_common import get_node
from .recipe_common import (
    RECIPE_CATEGORY_ALIASES,
    apply_tool_recipe,
    get_recipe_item,
    recipe_items,
)

DEFAULT_LIMIT = 50
CATEGORIES = tuple(RECIPE_CATEGORY_ALIASES)


def _add_scripts(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pre-script", help="UTF-8 file or '-' containing a prescript.")
    parser.add_argument("--post-script", help="UTF-8 file or '-' containing a postscript.")


def _add_storage(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--label", required=True)
    parser.add_argument("--library", required=True, help="HDA file, expanded directory, or Embedded.")
    parser.add_argument("--submenu", default="")
    parser.add_argument("--hidden", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing recipe key.")
    parser.add_argument("--expand-to-dir", action="store_true")
    _add_scripts(parser)


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("recipe", help="Discover, apply, create, and delete Houdini recipes.")
    commands = parser.add_subparsers(dest="recipe_command", required=True)

    list_parser = commands.add_parser("list")
    list_parser.add_argument("--category", choices=CATEGORIES)
    list_parser.add_argument("--visible-only", action="store_true")
    list_parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    list_parser.set_defaults(handler=handle_list)

    find_parser = commands.add_parser("find")
    find_parser.add_argument("--query", required=True)
    find_parser.add_argument("--category", choices=CATEGORIES)
    find_parser.add_argument("--visible-only", action="store_true")
    find_parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    find_parser.set_defaults(handler=handle_find)

    get_parser = commands.add_parser("get")
    get_parser.add_argument("recipe_key")
    get_parser.set_defaults(handler=handle_get)

    apply_parser = commands.add_parser("apply")
    apply_commands = apply_parser.add_subparsers(dest="recipe_apply_command", required=True)
    tool_apply = apply_commands.add_parser("tool")
    tool_apply.add_argument("recipe_key")
    tool_apply.add_argument("--parent", required=True)
    tool_apply.set_defaults(handler=handle_apply_tool)
    decoration_apply = apply_commands.add_parser("decoration")
    decoration_apply.add_argument("recipe_key")
    decoration_apply.add_argument("--node", required=True)
    decoration_apply.set_defaults(handler=handle_apply_decoration)
    node_apply = apply_commands.add_parser("node-preset")
    node_apply.add_argument("recipe_key")
    node_apply.add_argument("--node", required=True)
    node_apply.set_defaults(handler=handle_apply_node_preset)
    parm_apply = apply_commands.add_parser("parm-preset")
    parm_apply.add_argument("recipe_key")
    parm_apply.add_argument("--parm", required=True)
    parm_apply.add_argument(
        "--multiparm-operation",
        choices=("set", "set_from_index", "insert_at_index", "insert_first", "append"),
        default="",
    )
    parm_apply.add_argument("--multiparm-start-index", type=int, default=0)
    parm_apply.set_defaults(handler=handle_apply_parm_preset)

    create_parser = commands.add_parser("create")
    create_commands = create_parser.add_subparsers(dest="recipe_create_command", required=True)
    tool_create = create_commands.add_parser("tool")
    tool_create.add_argument("recipe_key")
    tool_create.add_argument("--anchor", required=True)
    tool_create.add_argument("--items", nargs="+", required=True)
    tool_create.add_argument("--icon", default="BUTTONS_recipe")
    tool_create.add_argument("--flags", action="store_true")
    _add_storage(tool_create)
    tool_create.set_defaults(handler=handle_create_tool)

    decoration_create = create_commands.add_parser("decoration")
    decoration_create.add_argument("recipe_key")
    decoration_create.add_argument("--central", required=True)
    decoration_create.add_argument("--items", nargs="+", required=True)
    decoration_create.add_argument("--node-type-pattern", default="")
    decoration_create.add_argument("--central-parms", nargs="*")
    decoration_create.add_argument("--flags", action="store_true")
    _add_storage(decoration_create)
    decoration_create.set_defaults(handler=handle_create_decoration)

    node_create = create_commands.add_parser("node-preset")
    node_create.add_argument("recipe_key")
    node_create.add_argument("--node", required=True)
    node_create.add_argument("--parms", nargs="*")
    node_create.add_argument("--node-type-pattern", default="")
    node_create.add_argument("--children", action="store_true")
    node_create.add_argument("--editables", action="store_true")
    _add_storage(node_create)
    node_create.set_defaults(handler=handle_create_node_preset)

    parm_create = create_commands.add_parser("parm-preset")
    parm_create.add_argument("recipe_key")
    parm_create.add_argument("--parm", required=True)
    parm_create.add_argument("--parm-type-pattern", default="")
    parm_create.add_argument("--parm-name-pattern", default="")
    parm_create.add_argument("--node-type-pattern", default="")
    parm_create.add_argument(
        "--multiparm-operation",
        choices=("set", "set_from_index", "insert_at_index", "insert_first", "append"),
        default="set",
    )
    parm_create.add_argument("--multiparm-start-index", type=int, default=0)
    parm_create.add_argument("--multiparm-end-index", type=int, default=-1)
    _add_storage(parm_create)
    parm_create.set_defaults(handler=handle_create_parm_preset)


def _validate_limit(limit: int) -> None:
    if limit <= 0:
        raise ValueError(f"Limit must be positive: {limit}")


def handle_list(args: argparse.Namespace) -> dict:
    _validate_limit(args.limit)
    with connect(args.host, args.port) as session:
        rows = recipe_items(session, category=args.category, visible_only=args.visible_only)
        return success_result(
            {"count": len(rows[: args.limit]), "items": rows[: args.limit]},
            meta={"truncated": len(rows) > args.limit, "total_matches": len(rows), "limit": args.limit},
        )


def handle_find(args: argparse.Namespace) -> dict:
    _validate_limit(args.limit)
    query = args.query.lower()
    with connect(args.host, args.port) as session:
        rows = [
            row
            for row in recipe_items(session, category=args.category, visible_only=args.visible_only)
            if query in row["key"].lower() or query in row["label"].lower()
        ]
        return success_result(
            {"query": args.query, "count": len(rows[: args.limit]), "items": rows[: args.limit]},
            meta={"truncated": len(rows) > args.limit, "total_matches": len(rows), "limit": args.limit},
        )


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        return success_result(get_recipe_item(session, args.recipe_key))


def _ensure_category(session: Any, recipe_key: str, expected: str) -> None:
    actual = get_recipe_item(session, recipe_key)["category"]
    if actual != expected:
        raise ValueError(f"Recipe category mismatch: expected {expected}, got {actual}")


def _remote_apply(session: Any, code: str, values: dict[str, Any]) -> dict[str, Any]:
    namespace = session.connection.namespace
    for key, value in values.items():
        namespace[key] = value
    session.connection.execute(code)
    return json.loads(localize(namespace["_houdini_cli_recipe_result_json"]))


def handle_apply_tool(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        _ensure_category(session, args.recipe_key, "tool")
        return success_result(apply_tool_recipe(session, get_node(session, args.parent), args.recipe_key))


def handle_apply_decoration(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        _ensure_category(session, args.recipe_key, "decoration")
        result = _remote_apply(
            session,
            """
import hou as _houdini_cli_hou, json as _houdini_cli_json
_r = _houdini_cli_hou.data.applyDecorationRecipe(
    _recipe_key, _houdini_cli_hou.node(_node_path),
    drop_on_wire=False, click_to_place=False, avoid_overlap=False, frame=False)
_houdini_cli_recipe_result_json = _houdini_cli_json.dumps({
    "recipe": _recipe_key, "category": "decoration",
    "central_node": _r["central_node"].path(),
    "items": {str(k): v.path() for k, v in _r.get("items", {}).items()},
    "parms": [p.name() for p in _r.get("central_parms", ())],
})
""",
            {"_recipe_key": args.recipe_key, "_node_path": args.node},
        )
        return success_result(result)


def handle_apply_node_preset(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        _ensure_category(session, args.recipe_key, "node-preset")
        result = _remote_apply(
            session,
            """
import hou as _houdini_cli_hou, json as _houdini_cli_json
_r = _houdini_cli_hou.data.applyNodePresetRecipe(_recipe_key, _houdini_cli_hou.node(_node_path))
_houdini_cli_recipe_result_json = _houdini_cli_json.dumps({
    "recipe": _recipe_key, "category": "node-preset", "node": _r["node"].path(),
    "parms": [p.name() for p in _r.get("parms", ())],
})
""",
            {"_recipe_key": args.recipe_key, "_node_path": args.node},
        )
        return success_result(result)


def handle_apply_parm_preset(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        _ensure_category(session, args.recipe_key, "parm-preset")
        result = _remote_apply(
            session,
            """
import hou as _houdini_cli_hou, json as _houdini_cli_json
_p = _houdini_cli_hou.parmTuple(_parm_path) or _houdini_cli_hou.parm(_parm_path)
_r = _houdini_cli_hou.data.applyParmPresetRecipe(
    _recipe_key, _p, multiparm_operation=_multiparm_operation,
    multiparm_start_index=_multiparm_start_index)
_rp = _r.get("parm")
_houdini_cli_recipe_result_json = _houdini_cli_json.dumps({
    "recipe": _recipe_key, "category": "parm-preset", "node": _r["node"].path(),
    "parm": _rp.name() if _rp is not None else None,
})
""",
            {
                "_recipe_key": args.recipe_key,
                "_parm_path": args.parm,
                "_multiparm_operation": args.multiparm_operation,
                "_multiparm_start_index": args.multiparm_start_index,
            },
        )
        return success_result(result)


def _scripts(args: argparse.Namespace) -> tuple[str, str]:
    return (
        read_text_input(args.pre_script) if args.pre_script else "",
        read_text_input(args.post_script) if args.post_script else "",
    )


def _prepare_create(session: Any, args: argparse.Namespace) -> tuple[str, str]:
    existing = session.hou.dataNodeTypeCategory().nodeTypes().get(args.recipe_key)
    if existing is not None:
        if not args.force:
            raise ValueError(f"Recipe already exists; use --force to overwrite: {args.recipe_key}")
    return _scripts(args)


def _created_summary(session: Any, recipe_key: str) -> dict[str, Any]:
    return {"created": True, **get_recipe_item(session, recipe_key)}


def handle_create_tool(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        pre, post = _prepare_create(session, args)
        anchor = get_node(session, args.anchor)
        items = tuple(get_node(session, path) for path in args.items)
        session.hou.data.saveToolRecipe(
            args.recipe_key, args.label, args.library, anchor, items=items,
            tab_submenu=args.submenu, icon=args.icon, visible=not args.hidden,
            flags=args.flags, prescript=pre, postscript=post, expand_to_dir=args.expand_to_dir,
        )
        return success_result(_created_summary(session, args.recipe_key))


def handle_create_decoration(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        pre, post = _prepare_create(session, args)
        central = get_node(session, args.central)
        items = tuple(get_node(session, path) for path in args.items)
        central_parms: bool | tuple[str, ...] = tuple(args.central_parms) if args.central_parms else True
        session.hou.data.saveDecorationRecipe(
            args.recipe_key, args.label, args.library, central, items,
            nodetype_patterns=args.node_type_pattern, submenu=args.submenu,
            visible=not args.hidden, central_parms=central_parms, flags=args.flags,
            prescript=pre, postscript=post, expand_to_dir=args.expand_to_dir,
        )
        return success_result(_created_summary(session, args.recipe_key))


def handle_create_node_preset(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        pre, post = _prepare_create(session, args)
        node = get_node(session, args.node)
        parms: bool | tuple[str, ...] = tuple(args.parms) if args.parms else True
        session.hou.data.saveNodePresetRecipe(
            args.recipe_key, args.label, args.library, node,
            nodetype_patterns=args.node_type_pattern, submenu=args.submenu,
            visible=not args.hidden, parms=parms, children=args.children, editables=args.editables,
            prescript=pre, postscript=post, expand_to_dir=args.expand_to_dir,
        )
        return success_result(_created_summary(session, args.recipe_key))


def handle_create_parm_preset(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        pre, post = _prepare_create(session, args)
        parameter = session.hou.parmTuple(args.parm) or session.hou.parm(args.parm)
        if parameter is None:
            raise ValueError(f"Parameter not found: {args.parm}")
        session.hou.data.saveParmPresetRecipe(
            args.recipe_key, args.label, args.library, parameter,
            parmtype_patterns=args.parm_type_pattern, parmname_patterns=args.parm_name_pattern,
            nodetype_patterns=args.node_type_pattern, submenu=args.submenu,
            visible=not args.hidden, multiparm_operation=args.multiparm_operation,
            multiparm_start_index=args.multiparm_start_index,
            multiparm_end_index=args.multiparm_end_index,
            prescript=pre, postscript=post, expand_to_dir=args.expand_to_dir,
        )
        return success_result(_created_summary(session, args.recipe_key))
