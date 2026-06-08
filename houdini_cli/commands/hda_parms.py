"""HDA parameter-interface commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .hda_common import definition_for_node, parm_tree, save_definition
from .node_common import get_node
from .parm import _read_json_input


def handle_parms_inspect(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        return success_result(
            {
                "asset_node": args.asset_node,
                "parms": parm_tree(definition.parmTemplateGroup().entries()),
            }
        )


def _template_from_spec(session: Any, spec: dict[str, Any]) -> Any:
    kind = spec["type"]
    name = spec["name"]
    label = spec.get("label", name)
    default = spec.get("default")
    if kind == "float":
        return session.hou.FloatParmTemplate(
            name, label, 1, default_value=(float(default or 0.0),)
        )
    if kind == "int":
        return session.hou.IntParmTemplate(name, label, 1, default_value=(int(default or 0),))
    if kind == "toggle":
        return session.hou.ToggleParmTemplate(name, label, bool(default))
    if kind == "string":
        return session.hou.StringParmTemplate(name, label, 1, default_value=(default or "",))
    if kind == "menu":
        items = tuple(spec["items"])
        labels = tuple(spec.get("labels", items))
        value = default if isinstance(default, int) else items.index(default) if default in items else 0
        return session.hou.MenuParmTemplate(name, label, items, labels, default_value=value)
    raise ValueError(f"Unsupported parameter type: {kind}")


def handle_parms_apply(args: argparse.Namespace) -> dict:
    payload = _read_json_input(args.input)
    with connect(args.host, args.port) as session:
        node = get_node(session, args.asset_node)
        definition = definition_for_node(node)
        group = (
            session.hou.ParmTemplateGroup()
            if args.replace_all
            else definition.parmTemplateGroup()
        )
        for folder_spec in payload.get("folders", []):
            folder = session.hou.FolderParmTemplate(
                folder_spec["name"], folder_spec.get("label", folder_spec["name"])
            )
            for spec in folder_spec.get("parms", []):
                folder.addParmTemplate(_template_from_spec(session, spec))
            group.append(folder)
        definition.setParmTemplateGroup(group)
        library = save_definition(definition)
        node.matchCurrentDefinition()
        return success_result(
            {"asset_node": args.asset_node, "library": library, "applied": True}
        )


def handle_parms_promote(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.asset_node)
        definition = definition_for_node(node)
        internal = node.parm(args.internal_parm)
        if internal is None:
            raise ValueError(f"Internal parameter not found: {args.internal_parm}")
        template = internal.parmTemplate().clone()
        template.setName(args.name)
        if args.label:
            template.setLabel(args.label)
        if args.default == "current":
            value = localize(internal.eval())
            if template.numComponents() == 1:
                try:
                    template.setDefaultValue((value,))
                except TypeError:
                    template.setDefaultValue(value)
        group = definition.parmTemplateGroup()
        if args.folder:
            folder = group.find(args.folder)
            if folder is None:
                group.append(session.hou.FolderParmTemplate(args.folder, args.folder))
            updated = group.find(args.folder).clone()
            updated.addParmTemplate(template)
            group.replace(args.folder, updated)
        else:
            group.append(template)
        definition.setParmTemplateGroup(group)
        save_definition(definition)
        node.matchCurrentDefinition()
        internal = node.parm(args.internal_parm)
        outer = node.parm(args.name)
        function = "chs" if template.type() == session.hou.parmTemplateType.String else "ch"
        internal.setExpression(
            f'{function}("../{args.name}")', session.hou.exprLanguage.Hscript
        )
        definition.updateFromNode(node)
        save_definition(definition)
        node.matchCurrentDefinition()
        return success_result(
            {
                "asset_node": args.asset_node,
                "promoted": args.name,
                "outer_parm": localize(outer.path()) if outer else None,
            }
        )


def handle_parms_defaults(args: argparse.Namespace) -> dict:
    if not args.from_current:
        raise ValueError("Currently requires --from-current")
    with connect(args.host, args.port) as session:
        node = get_node(session, args.asset_node)
        definition = definition_for_node(node)
        group = definition.parmTemplateGroup()
        count = 0
        visited = set()
        for parm in node.parms():
            name = localize(parm.tuple().name())
            if name in visited:
                continue
            visited.add(name)
            template = group.find(name)
            if template is None:
                continue
            updated = template.clone()
            values = [localize(item.eval()) for item in parm.tuple()]
            try:
                scalar = len(values) == 1 and localize(updated.type().name()) in {"Menu", "Toggle"}
                updated.setDefaultValue(values[0] if scalar else tuple(values))
            except Exception:
                continue
            group.replace(name, updated)
            count += 1
        definition.setParmTemplateGroup(group)
        library = save_definition(definition)
        node.matchCurrentDefinition()
        return success_result(
            {
                "asset_node": args.asset_node,
                "updated_defaults": count,
                "library": library,
            }
        )

