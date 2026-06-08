"""HDA parameter-interface commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .hda_common import definition_for_node, parm_tree, save_definition
from .node_common import get_node
from .parm import _read_json_input

_FOLDER_TYPES = {
    "tabs": "Tabs",
    "simple": "Simple",
    "collapsible": "Collapsible",
    "radio": "RadioButtons",
}
_RAMP_BASES = {
    "linear": "Linear",
    "constant": "Constant",
    "catmull_rom": "CatmullRom",
    "monotone_cubic": "MonotoneCubic",
    "bezier": "Bezier",
    "bspline": "BSpline",
    "hermite": "Hermite",
}
_COLOR_TYPES = {"rgb": "RGB", "hsv": "HSV", "hsl": "HSL", "lab": "LAB", "xyz": "XYZ"}


def handle_parms_inspect(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        return success_result(
            {
                "asset_node": args.asset_node,
                "parms": parm_tree(definition.parmTemplateGroup().entries()),
            }
        )


def _callback_language(session: Any, name: str) -> Any:
    if name == "python":
        return session.hou.scriptLanguage.Python
    if name == "hscript":
        return session.hou.scriptLanguage.Hscript
    raise ValueError(f"Unsupported callback language: {name}")


def _apply_common_options(session: Any, template: Any, spec: dict[str, Any]) -> Any:
    callback = spec.get("callback")
    if callback is not None:
        template.setScriptCallback(callback)
        template.setScriptCallbackLanguage(
            _callback_language(session, spec.get("callback_language", "python"))
        )
    if "help" in spec:
        template.setHelp(spec["help"])
    if "hidden" in spec:
        template.hide(bool(spec["hidden"]))
    if "join_with_next" in spec:
        template.setJoinWithNext(bool(spec["join_with_next"]))
    return template


def _ramp_template(session: Any, spec: dict[str, Any], name: str, label: str) -> Any:
    kind = spec["type"]
    ramp_type = (
        session.hou.rampParmType.Color
        if kind == "color_ramp"
        else session.hou.rampParmType.Float
    )
    basis_name = spec.get("basis", "linear")
    if basis_name not in _RAMP_BASES:
        raise ValueError(f"Unsupported ramp basis: {basis_name}")
    basis = getattr(session.hou.rampBasis, _RAMP_BASES[basis_name])
    kwargs = {
        "default_value": int(spec.get("keys", 2)),
        "default_basis": basis,
        "show_controls": bool(spec.get("show_controls", True)),
    }
    if kind == "color_ramp":
        color_name = spec.get("color_space", "rgb")
        if color_name not in _COLOR_TYPES:
            raise ValueError(f"Unsupported ramp color space: {color_name}")
        kwargs["color_type"] = getattr(session.hou.colorType, _COLOR_TYPES[color_name])
    return session.hou.RampParmTemplate(name, label, ramp_type, **kwargs)


def _template_from_spec(session: Any, spec: dict[str, Any]) -> Any:
    kind = spec["type"]
    name = spec["name"]
    label = spec.get("label", name)
    default = spec.get("default")
    if kind == "float":
        template = session.hou.FloatParmTemplate(
            name, label, 1, default_value=(float(default or 0.0),)
        )
    elif kind == "int":
        template = session.hou.IntParmTemplate(
            name, label, 1, default_value=(int(default or 0),)
        )
    elif kind == "toggle":
        template = session.hou.ToggleParmTemplate(name, label, bool(default))
    elif kind == "string":
        template = session.hou.StringParmTemplate(
            name, label, 1, default_value=(default or "",)
        )
    elif kind == "menu":
        items = tuple(spec["items"])
        labels = tuple(spec.get("labels", items))
        value = default if isinstance(default, int) else items.index(default) if default in items else 0
        template = session.hou.MenuParmTemplate(
            name, label, items, labels, default_value=value
        )
    elif kind in {"float_ramp", "color_ramp"}:
        template = _ramp_template(session, spec, name, label)
    else:
        raise ValueError(f"Unsupported parameter type: {kind}")
    return _apply_common_options(session, template, spec)


def _folder_from_spec(session: Any, spec: dict[str, Any]) -> Any:
    folder_type_name = spec.get("folder_type", "tabs")
    if folder_type_name not in _FOLDER_TYPES:
        raise ValueError(f"Unsupported folder type: {folder_type_name}")
    folder = session.hou.FolderParmTemplate(
        spec["name"],
        spec.get("label", spec["name"]),
        folder_type=getattr(session.hou.folderType, _FOLDER_TYPES[folder_type_name]),
    )
    for item in spec.get("items", spec.get("parms", [])):
        folder.addParmTemplate(_layout_template_from_spec(session, item))
    return folder


def _layout_template_from_spec(session: Any, spec: dict[str, Any]) -> Any:
    kind = spec["type"]
    if kind == "folder":
        return _folder_from_spec(session, spec)
    if kind == "heading":
        return session.hou.LabelParmTemplate(
            spec["name"],
            spec.get("label", spec["name"]),
            is_label_hidden=bool(spec.get("hide_label", False)),
        )
    if kind == "separator":
        return session.hou.SeparatorParmTemplate(spec["name"])
    return _template_from_spec(session, spec)


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
            normalized = {"type": "folder", **folder_spec}
            group.append(_folder_from_spec(session, normalized))
        for item in payload.get("items", []):
            group.append(_layout_template_from_spec(session, item))
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
