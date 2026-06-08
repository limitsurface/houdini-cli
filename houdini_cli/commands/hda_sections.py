"""HDA section, script, and Tab-menu tool commands."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.input import read_text_input
from .hda_common import definition_for_node, save_definition
from .node_common import get_node

SCRIPT_SECTIONS = {"OnCreated", "OnLoaded", "OnUpdated", "PythonModule"}


def tool_xml(submenu: str, category: str) -> str:
    context = "COP" if category.upper().startswith("COP") else "SOP"
    script = (
        "import coptoolutils\ncoptoolutils.genericTool(kwargs, '$HDA_NAME')"
        if context == "COP"
        else "import soptoolutils\nsoptoolutils.genericTool(kwargs, '$HDA_NAME')"
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
    <toolMenuContext name="viewer"><contextNetType>{context}</contextNetType></toolMenuContext>
    <toolMenuContext name="network"><contextOpType>$HDA_TABLE_AND_NAME</contextOpType></toolMenuContext>
    <toolSubmenu>{submenu}</toolSubmenu>
    <script scriptType="python"><![CDATA[{script}]]></script>
  </tool>
</shelfDocument>
"""


def handle_section_list(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        rows = [
            {"name": localize(name), "size": int(localize(section.size()))}
            for name, section in definition.sections().items()
        ]
        return success_result({"asset_node": args.asset_node, "sections": rows})


def handle_section_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        section = definition.sections().get(args.name)
        if section is None:
            raise ValueError(f"HDA section not found: {args.name}")
        text = localize(section.contents())
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(text)
            return success_result({"name": args.name, "output": args.output, "size": len(text)})
        return success_result({"name": args.name, "contents": text})


def handle_section_set(args: argparse.Namespace) -> dict:
    text = read_text_input(args.input)
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        definition.addSection(args.name, text)
        library = None if args.no_save else save_definition(definition)
        return success_result(
            {"name": args.name, "size": len(text), "library": library, "applied": True}
        )


def handle_section_delete(args: argparse.Namespace) -> dict:
    if not args.force:
        raise ValueError("Section deletion requires --force")
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        if args.name not in definition.sections():
            raise ValueError(f"HDA section not found: {args.name}")
        definition.removeSection(args.name)
        library = None if args.no_save else save_definition(definition)
        return success_result({"name": args.name, "library": library, "deleted": True})


def handle_script_get(args: argparse.Namespace) -> dict:
    return handle_section_get(args)


def handle_script_set(args: argparse.Namespace) -> dict:
    text = read_text_input(args.input)
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        definition.addSection(args.name, text)
        definition.setExtraFileOption(f"{args.name}/IsPython", True)
        library = None if args.no_save else save_definition(definition)
        return success_result(
            {"name": args.name, "size": len(text), "library": library, "applied": True}
        )


def handle_script_delete(args: argparse.Namespace) -> dict:
    return handle_section_delete(args)


def handle_tool_inspect(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        section = definition.sections().get("Tools.shelf")
        return success_result(
            {
                "asset_node": args.asset_node,
                "tools": [localize(name) for name in definition.tools().keys()],
                "contents": localize(section.contents()) if section else None,
            }
        )


def handle_tool_set(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        if args.icon:
            definition.setIcon(args.icon)
        definition.addSection("Tools.shelf", tool_xml(args.submenu, args.context))
        library = save_definition(definition)
        return success_result(
            {"submenu": args.submenu, "context": args.context, "library": library, "applied": True}
        )


def handle_tool_remove(args: argparse.Namespace) -> dict:
    if not args.force:
        raise ValueError("Tool removal requires --force")
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        if "Tools.shelf" in definition.sections():
            definition.removeSection("Tools.shelf")
        library = save_definition(definition)
        return success_result({"library": library, "removed": True})
