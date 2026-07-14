"""HDA parameter-interface commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.input import read_json_input
from .hda_common import definition_for_node, parm_tree_in_houdini, save_definition
from .node_common import get_node

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
        node = get_node(session, args.asset_node)
        if getattr(args, "tree", False):
            return success_result(
                {
                    "asset_node": args.asset_node,
                    "parms": parm_tree_in_houdini(session, args.asset_node),
                }
            )
        rows = _flat_parm_rows_in_houdini(
            session,
            args.asset_node,
            folder_filter=getattr(args, "folder", None),
            name_filter=getattr(args, "name", None),
            include_values=getattr(args, "values", False),
            include_defaults=getattr(args, "defaults", False),
        )
        cols = ["name", "label", "type", "folder"]
        if getattr(args, "values", False):
            cols.append("value")
        if getattr(args, "defaults", False):
            cols.append("default")
        return success_result(
            {
                "asset_node": args.asset_node,
                "count": len(rows),
                "cols": cols,
                "rows": rows,
            }
        )


def _template_default(template: Any) -> Any:
    method = getattr(template, "defaultValue", None)
    if not callable(method):
        return None
    try:
        return localize(method())
    except Exception:
        return None


def _flat_parm_rows(
    node: Any,
    entries: Any,
    *,
    folder_filter: str | None = None,
    name_filter: str | None = None,
    include_values: bool = False,
    include_defaults: bool = False,
    parents: tuple[str, ...] = (),
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    folder_needle = folder_filter.lower() if folder_filter else None
    name_needle = name_filter.lower() if name_filter else None
    for template in entries:
        name = str(localize(template.name()))
        label = str(localize(template.label()))
        type_name = str(localize(template.type().name()))
        if type_name in {"Folder", "FolderSet"}:
            rows.extend(
                _flat_parm_rows(
                    node,
                    template.parmTemplates(),
                    folder_filter=folder_filter,
                    name_filter=name_filter,
                    include_values=include_values,
                    include_defaults=include_defaults,
                    parents=(*parents, label),
                )
            )
            continue
        if type_name in {"Button", "Folder", "FolderSet", "Label", "Separator"}:
            continue
        folder_path = "/".join(parents)
        if folder_needle and folder_needle not in folder_path.lower():
            continue
        if name_needle and name_needle not in name.lower() and name_needle not in label.lower():
            continue
        row: list[Any] = [name, label, type_name, folder_path]
        if include_values:
            parm = node.parm(name)
            row.append(localize(parm.eval()) if parm is not None else None)
        if include_defaults:
            row.append(_template_default(template))
        rows.append(row)
    return rows


def _folder_rows(entries: Any, parents: tuple[str, ...] = ()) -> list[list[Any]]:
    rows = []
    for template in entries:
        if str(localize(template.type().name())) not in {"Folder", "FolderSet"}:
            continue
        label = str(localize(template.label()))
        path = "/".join((*parents, label))
        children = list(template.parmTemplates())
        rows.append([str(localize(template.name())), label, path, len(children)])
        rows.extend(_folder_rows(children, (*parents, label)))
    return rows


def _flat_parm_rows_in_houdini(
    session: Any,
    node_path: str,
    *,
    folder_filter: str | None = None,
    name_filter: str | None = None,
    include_values: bool = False,
    include_defaults: bool = False,
) -> list[list[Any]]:
    if not hasattr(session, "connection"):
        node = get_node(session, node_path)
        definition = definition_for_node(node)
        return _flat_parm_rows(
            node,
            definition.parmTemplateGroup().entries(),
            folder_filter=folder_filter,
            name_filter=name_filter,
            include_values=include_values,
            include_defaults=include_defaults,
        )

    source = r"""
import hou

SKIPPED_HDA_TEMPLATE_TYPES = {"Button", "Folder", "FolderSet", "Label", "Separator"}

def _houdini_cli_template_default(template):
    method = getattr(template, "defaultValue", None)
    if not callable(method):
        return None
    try:
        return method()
    except Exception:
        return None

def _houdini_cli_hda_flat_rows(node_path, folder_filter, name_filter, include_values, include_defaults):
    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)
    definition = node.type().definition()
    if definition is None:
        raise ValueError("Node is not an HDA instance: " + node_path)

    folder_needle = folder_filter.lower() if folder_filter else None
    name_needle = name_filter.lower() if name_filter else None

    def walk(entries, parents=()):
        rows = []
        for template in entries:
            name = template.name()
            label = template.label()
            type_name = template.type().name()
            if type_name in {"Folder", "FolderSet"}:
                rows.extend(walk(template.parmTemplates(), parents + (label,)))
                continue
            if type_name in SKIPPED_HDA_TEMPLATE_TYPES:
                continue

            folder_path = "/".join(parents)
            if folder_needle and folder_needle not in folder_path.lower():
                continue
            if name_needle and name_needle not in name.lower() and name_needle not in label.lower():
                continue

            row = [name, label, type_name, folder_path]
            if include_values:
                parm = node.parm(name)
                row.append(parm.eval() if parm is not None else None)
            if include_defaults:
                row.append(_houdini_cli_template_default(template))
            rows.append(row)
        return rows

    return walk(definition.parmTemplateGroup().entries())
"""
    session.connection.execute(source)
    return localize(
        session.connection.eval(
            "_houdini_cli_hda_flat_rows("
            f"{node_path!r}, {folder_filter!r}, {name_filter!r}, "
            f"{bool(include_values)!r}, {bool(include_defaults)!r})"
        )
    )


def _folder_rows_in_houdini(session: Any, node_path: str) -> list[list[Any]]:
    if not hasattr(session, "connection"):
        definition = definition_for_node(get_node(session, node_path))
        return _folder_rows(definition.parmTemplateGroup().entries())

    source = r"""
import hou

def _houdini_cli_hda_folder_rows(node_path):
    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)
    definition = node.type().definition()
    if definition is None:
        raise ValueError("Node is not an HDA instance: " + node_path)

    def walk(entries, parents=()):
        rows = []
        for template in entries:
            if template.type().name() not in {"Folder", "FolderSet"}:
                continue
            label = template.label()
            path = "/".join(parents + (label,))
            children = list(template.parmTemplates())
            rows.append([template.name(), label, path, len(children)])
            rows.extend(walk(children, parents + (label,)))
        return rows

    return walk(definition.parmTemplateGroup().entries())
"""
    session.connection.execute(source)
    return localize(session.connection.eval(f"_houdini_cli_hda_folder_rows({node_path!r})"))


def handle_parms_folders(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        rows = _folder_rows_in_houdini(session, args.asset_node)
        return success_result(
            {
                "asset_node": args.asset_node,
                "count": len(rows),
                "cols": ["name", "label", "path", "children"],
                "rows": rows,
            }
        )


def handle_parms_locate(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        get_node(session, args.asset_node)
        rows = _flat_parm_rows_in_houdini(
            session,
            args.asset_node,
            name_filter=args.parm_name,
            include_values=True,
            include_defaults=True,
        )
        exact = [row for row in rows if row[0] == args.parm_name]
        if not exact:
            raise ValueError(f"Published HDA parameter not found: {args.parm_name}")
        return success_result(
            {
                "asset_node": args.asset_node,
                "cols": ["name", "label", "type", "folder", "value", "default"],
                "row": exact[0],
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
    payload = read_json_input(args.input)
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
        folder = getattr(args, "folder", None)
        names = None
        if folder:
            rows = _flat_parm_rows_in_houdini(
                session,
                args.asset_node,
                folder_filter=folder,
            )
            names = [row[0] for row in rows]
            if not names:
                raise ValueError(f"No published HDA parameters found below folder: {folder}")
        result = _set_defaults_from_current_in_houdini(
            session,
            args.asset_node,
            names=names,
        )
        return success_result(
            {
                "asset_node": args.asset_node,
                "folder": folder,
                "updated_defaults": result["updated_defaults"],
                "library": result["library"],
            }
        )


def _set_defaults_from_current_in_houdini(
    session: Any,
    node_path: str,
    *,
    names: list[str] | None = None,
) -> dict[str, Any]:
    allowed_names = set(names) if names is not None else None
    if not hasattr(session, "connection"):
        node = get_node(session, node_path)
        definition = definition_for_node(node)
        group = definition.parmTemplateGroup()
        count = 0
        visited = set()
        for parm in node.parms():
            name = localize(parm.tuple().name())
            if name in visited:
                continue
            visited.add(name)
            if allowed_names is not None and name not in allowed_names:
                continue
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
        return {"updated_defaults": count, "library": library}

    source = r"""
import hou

def _houdini_cli_hda_defaults_from_current(node_path, names):
    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)
    definition = node.type().definition()
    if definition is None:
        raise ValueError("Node is not an HDA instance: " + node_path)

    group = definition.parmTemplateGroup()
    allowed_names = set(names) if names is not None else None
    count = 0
    visited = set()
    for parm in node.parms():
        name = parm.tuple().name()
        if name in visited:
            continue
        visited.add(name)
        if allowed_names is not None and name not in allowed_names:
            continue
        template = group.find(name)
        if template is None:
            continue
        updated = template.clone()
        values = [item.eval() for item in parm.tuple()]
        try:
            scalar = len(values) == 1 and updated.type().name() in {"Menu", "Toggle"}
            updated.setDefaultValue(values[0] if scalar else tuple(values))
        except Exception:
            continue
        group.replace(name, updated)
        count += 1

    definition.setParmTemplateGroup(group)
    library = definition.libraryFilePath()
    definition.save(library)
    node.matchCurrentDefinition()
    return {"updated_defaults": count, "library": library}
"""
    session.connection.execute(source)
    return localize(
        session.connection.eval(
            f"_houdini_cli_hda_defaults_from_current({node_path!r}, {names!r})"
        )
    )
