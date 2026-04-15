"""Shelf commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    shelf_parser = subparsers.add_parser("shelf", help="Inspect and modify shelf tabs and tools.")
    shelf_subparsers = shelf_parser.add_subparsers(dest="shelf_command", required=True)

    list_parser = shelf_subparsers.add_parser("list", help="List shelves.")
    list_parser.set_defaults(handler=handle_list)

    tools_parser = shelf_subparsers.add_parser("tools", help="List tools on one shelf.")
    tools_parser.add_argument("shelf_name", help="Shelf internal name.")
    tools_parser.set_defaults(handler=handle_tools)

    find_parser = shelf_subparsers.add_parser("find", help="Search shelves and tools.")
    find_parser.add_argument("--query", required=True, help="Case-insensitive search text.")
    find_parser.set_defaults(handler=handle_find)

    tool_parser = shelf_subparsers.add_parser("tool", help="Create, edit, or delete shelf tools.")
    tool_subparsers = tool_parser.add_subparsers(dest="shelf_tool_command", required=True)

    add_parser = tool_subparsers.add_parser("add", help="Add a new tool to a shelf.")
    add_parser.add_argument("shelf_name", help="Shelf internal name.")
    add_parser.add_argument("tool_name", help="Tool internal name.")
    add_parser.add_argument("--label", required=True, help="Tool label.")
    add_parser.add_argument("--input", required=True, help="File path or '-' to read script from stdin.")
    add_parser.set_defaults(handler=handle_tool_add)

    edit_parser = tool_subparsers.add_parser("edit", help="Edit an existing tool.")
    edit_parser.add_argument("tool_name", help="Tool internal name.")
    edit_parser.add_argument("--label", help="Updated tool label.")
    edit_parser.add_argument("--shelf", dest="shelf_name", help="Ensure the tool is present on this shelf.")
    edit_parser.add_argument("--input", help="File path or '-' to read replacement script from stdin.")
    edit_parser.set_defaults(handler=handle_tool_edit)

    delete_parser = tool_subparsers.add_parser("delete", help="Delete a tool from a shelf and remove it when orphaned.")
    delete_parser.add_argument("tool_name", help="Tool internal name.")
    delete_parser.add_argument("--shelf", dest="shelf_name", help="Optional shelf internal name to remove from.")
    delete_parser.set_defaults(handler=handle_tool_delete)


def _read_text_input(input_value: str) -> str:
    if input_value == "-":
        import sys

        return sys.stdin.read()
    with open(input_value, encoding="utf-8") as handle:
        return handle.read()


def _shelves(session: Any) -> dict[str, Any]:
    return session.hou.shelves.shelves()


def _tool_map(session: Any) -> dict[str, Any]:
    return session.hou.shelves.tools()


def _get_shelf(session: Any, shelf_name: str) -> Any:
    shelf = _shelves(session).get(shelf_name)
    if shelf is None:
        raise ValueError(f"Shelf not found: {shelf_name}")
    return shelf


def _get_tool(session: Any, tool_name: str) -> Any:
    tool = session.hou.shelves.tool(tool_name)
    if tool is None:
        raise ValueError(f"Tool not found: {tool_name}")
    return tool


def _shelf_row(shelf: Any) -> list[Any]:
    return [
        localize(shelf.name()),
        localize(shelf.label()),
        len(shelf.tools()),
        localize(shelf.filePath()),
    ]


def _tool_row(tool: Any) -> list[Any]:
    return [
        localize(tool.name()),
        localize(tool.label()),
    ]


def _find_tool_shelves(session: Any, tool_name: str) -> list[str]:
    owners: list[str] = []
    for shelf_name, shelf in _shelves(session).items():
        if any(localize(tool.name()) == tool_name for tool in shelf.tools()):
            owners.append(shelf_name)
    return owners


def handle_list(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        rows = [_shelf_row(shelf) for shelf in _shelves(session).values()]
        rows.sort(key=lambda row: row[0].lower())
        return success_result({"count": len(rows), "cols": ["n", "l", "tc", "fp"], "rows": rows})


def handle_tools(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        shelf = _get_shelf(session, args.shelf_name)
        rows = [_tool_row(tool) for tool in shelf.tools()]
        return success_result(
            {
                "shelf": {"n": localize(shelf.name()), "l": localize(shelf.label())},
                "count": len(rows),
                "cols": ["n", "l"],
                "rows": rows,
            }
        )


def handle_find(args: argparse.Namespace) -> dict:
    query = args.query.lower()
    with connect(args.host, args.port) as session:
        shelf_rows = []
        tool_rows = []
        for shelf_name, shelf in _shelves(session).items():
            name = localize(shelf.name())
            label = localize(shelf.label())
            if query in name.lower() or query in label.lower():
                shelf_rows.append([name, label])
            for tool in shelf.tools():
                tool_name = localize(tool.name())
                tool_label = localize(tool.label())
                if query in tool_name.lower() or query in tool_label.lower():
                    tool_rows.append([tool_name, tool_label, shelf_name])
        shelf_rows.sort(key=lambda row: row[0].lower())
        tool_rows.sort(key=lambda row: (row[2].lower(), row[0].lower()))
        return success_result(
            {
                "query": args.query,
                "shelves": {"count": len(shelf_rows), "cols": ["n", "l"], "rows": shelf_rows},
                "tools": {"count": len(tool_rows), "cols": ["n", "l", "s"], "rows": tool_rows},
            }
        )


def handle_tool_add(args: argparse.Namespace) -> dict:
    script = _read_text_input(args.input)
    with connect(args.host, args.port) as session:
        shelf = _get_shelf(session, args.shelf_name)
        if session.hou.shelves.tool(args.tool_name) is not None:
            raise ValueError(f"Tool already exists: {args.tool_name}")
        session.hou.shelves.beginChangeBlock()
        try:
            tool = session.hou.shelves.newTool(
                file_path=shelf.filePath(),
                name=args.tool_name,
                label=args.label,
                script=script,
                language=session.hou.scriptLanguage.Python,
            )
            shelf.setTools(tuple(list(shelf.tools()) + [tool]))
        finally:
            session.hou.shelves.endChangeBlock()
        return success_result(
            {
                "created": True,
                "tool": {"n": localize(tool.name()), "l": localize(tool.label()), "s": localize(shelf.name())},
            }
        )


def handle_tool_edit(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        tool = _get_tool(session, args.tool_name)
        applied: list[str] = []
        session.hou.shelves.beginChangeBlock()
        try:
            if args.label is not None:
                tool.setLabel(args.label)
                applied.append("label")
            if args.input is not None:
                tool.setScript(_read_text_input(args.input))
                applied.append("script")
            if args.shelf_name is not None:
                shelf = _get_shelf(session, args.shelf_name)
                tools = list(shelf.tools())
                if all(localize(item.name()) != args.tool_name for item in tools):
                    shelf.setTools(tuple(tools + [tool]))
                    applied.append("shelf")
        finally:
            session.hou.shelves.endChangeBlock()
        return success_result(
            {
                "updated": True,
                "applied": applied,
                "tool": {
                    "n": localize(tool.name()),
                    "l": localize(tool.label()),
                    "shelves": _find_tool_shelves(session, args.tool_name),
                },
            }
        )


def handle_tool_delete(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        tool = _get_tool(session, args.tool_name)
        removed_from: list[str] = []
        session.hou.shelves.beginChangeBlock()
        try:
            if args.shelf_name:
                target_shelves = [_get_shelf(session, args.shelf_name)]
            else:
                target_shelves = [shelf for shelf in _shelves(session).values() if any(localize(item.name()) == args.tool_name for item in shelf.tools())]
            if not target_shelves:
                raise ValueError(f"Tool is not present on any shelf: {args.tool_name}")

            for shelf in target_shelves:
                remaining = [item for item in shelf.tools() if localize(item.name()) != args.tool_name]
                if len(remaining) != len(shelf.tools()):
                    shelf.setTools(tuple(remaining))
                    removed_from.append(localize(shelf.name()))

            still_used = _find_tool_shelves(session, args.tool_name)
            destroyed = False
            if not still_used:
                tool.destroy()
                destroyed = True
        finally:
            session.hou.shelves.endChangeBlock()
        return success_result(
            {
                "deleted": True,
                "tool": args.tool_name,
                "removed_from": removed_from,
                "destroyed": destroyed,
            }
        )
