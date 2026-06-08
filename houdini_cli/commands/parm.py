"""Parameter commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.jsonio import load_json_input


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parm_parser = subparsers.add_parser("parm", help="Inspect and modify parameters.")
    parm_subparsers = parm_parser.add_subparsers(dest="parm_command", required=True)

    get_parser = parm_subparsers.add_parser("get", help="Get parameter value data.")
    get_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    get_parser.set_defaults(handler=handle_get)

    full_parser = parm_subparsers.add_parser("full", help="Get full structured parameter data.")
    full_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    full_parser.set_defaults(handler=handle_full)

    menu_parser = parm_subparsers.add_parser("menu", help="Get menu tokens and labels for a parameter.")
    menu_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    menu_parser.set_defaults(handler=handle_menu)

    set_parser = parm_subparsers.add_parser("set", help="Set a scalar or single string parameter value.")
    set_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    set_parser.add_argument("value", help="Parameter value.")
    set_parser.set_defaults(handler=handle_set)

    tuple_set_parser = parm_subparsers.add_parser("tuple-set", help="Set tuple parameter values.")
    tuple_set_parser.add_argument("parm_path", help="Tuple parameter path.")
    tuple_set_parser.add_argument("values", nargs="+", help="Tuple component values in order.")
    tuple_set_parser.set_defaults(handler=handle_tuple_set)

    text_set_parser = parm_subparsers.add_parser("text-set", help="Set a text parameter from stdin or a file.")
    text_set_parser.add_argument("parm_path", help="Parameter path.")
    text_set_parser.add_argument("--input", required=True, help="File path or '-' to read from stdin.")
    text_set_parser.set_defaults(handler=handle_text_set)

    full_set_parser = parm_subparsers.add_parser("full-set", help="Apply full structured parameter data.")
    full_set_parser.add_argument("parm_path", help="Parameter path.")
    full_set_parser.add_argument("--input", required=True, help="File path or '-' to read JSON from stdin.")
    full_set_parser.set_defaults(handler=handle_full_set)

    expression_parser = parm_subparsers.add_parser("expression", help="Inspect or modify parameter expressions.")
    expression_subparsers = expression_parser.add_subparsers(dest="parm_expression_command", required=True)

    expression_get_parser = expression_subparsers.add_parser("get", help="Read a parameter expression.")
    expression_get_parser.add_argument("parm_path")
    expression_get_parser.set_defaults(handler=handle_expression_get)

    expression_set_parser = expression_subparsers.add_parser("set", help="Set a parameter expression.")
    expression_set_parser.add_argument("parm_path")
    expression_set_parser.add_argument("--language", choices=("hscript", "python"), default="hscript")
    expression_set_parser.add_argument("--text", help="Expression text.")
    expression_set_parser.add_argument("--input", help="File path or '-' to read expression text.")
    expression_set_parser.set_defaults(handler=handle_expression_set)

    expression_clear_parser = expression_subparsers.add_parser("clear", help="Clear parameter keyframes/expressions.")
    expression_clear_parser.add_argument("parm_path")
    expression_clear_parser.add_argument("--keep-value", action="store_true")
    expression_clear_parser.set_defaults(handler=handle_expression_clear)

    reference_parser = parm_subparsers.add_parser("reference", help="Reference one parameter from another.")
    reference_parser.add_argument("target_parm", help="Parameter that will receive the reference.")
    reference_parser.add_argument("source_parm", help="Parameter to reference.")
    reference_mode = reference_parser.add_mutually_exclusive_group()
    reference_mode.add_argument("--relative", action="store_true", help="Use a relative HScript reference.")
    reference_mode.add_argument("--absolute", action="store_true", help="Use an absolute HScript reference.")
    reference_parser.set_defaults(handler=handle_reference)

    template_parser = parm_subparsers.add_parser("template", help="Inspect or modify parameter templates.")
    template_subparsers = template_parser.add_subparsers(dest="parm_template_command", required=True)

    template_get_parser = template_subparsers.add_parser("get", help="Read a parameter template summary.")
    template_get_parser.add_argument("parm_path")
    template_get_parser.add_argument("--target", choices=("instance", "definition"), default="instance")
    template_get_parser.set_defaults(handler=handle_template_get)

    template_set_parser = template_subparsers.add_parser("set", help="Apply a partial parameter template patch.")
    template_set_parser.add_argument("parm_path")
    template_set_parser.add_argument("--target", choices=("instance", "definition"), default="instance")
    template_set_parser.add_argument("--input", required=True, help="JSON file path or '-' for stdin.")
    template_set_parser.set_defaults(handler=handle_template_set)

    default_parser = parm_subparsers.add_parser("default", help="Set a parameter-template default.")
    default_subparsers = default_parser.add_subparsers(dest="parm_default_command", required=True)
    default_set_parser = default_subparsers.add_parser("set", help="Set a parameter-template default.")
    default_set_parser.add_argument("parm_path")
    default_set_parser.add_argument("--target", choices=("instance", "definition"), default="instance")
    default_source = default_set_parser.add_mutually_exclusive_group(required=True)
    default_source.add_argument("--current", action="store_true", help="Use the current parameter value.")
    default_source.add_argument("--value", help="JSON scalar or array.")
    default_set_parser.set_defaults(handler=handle_default_set)


def register_node_parms_parser(node_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parms_parser = node_subparsers.add_parser("parms", help="Discover parameters on one node.")
    parms_subparsers = parms_parser.add_subparsers(dest="node_parms_command", required=True)

    list_parser = parms_subparsers.add_parser("list", help="List parameters on one node.")
    list_parser.add_argument("node_path", help="Node path to inspect.")
    list_parser.add_argument("--non-default", action="store_true", help="Only include non-default parameters.")
    list_parser.add_argument("--max-parms", type=int, default=100, help="Maximum parameters to return.")
    list_parser.set_defaults(handler=handle_node_parms_list)

    find_parser = parms_subparsers.add_parser("find", help="Search parameters on one node.")
    find_parser.add_argument("node_path", help="Node path to inspect.")
    find_parser.add_argument("--name", help="Case-insensitive partial parm name match.")
    find_parser.add_argument("--type", dest="parm_type", help="Exact parm template type match.")
    find_parser.add_argument("--non-default", action="store_true", help="Only include non-default parameters.")
    find_parser.add_argument("--max-parms", type=int, default=100, help="Maximum parameters to return.")
    find_parser.set_defaults(handler=handle_node_parms_find)


def _get_parm(session: Any, parm_path: str) -> Any:
    parm = session.hou.parm(parm_path)
    if parm is None:
        raise ValueError(f"Parameter not found: {parm_path}")
    return parm


def _get_parm_tuple(session: Any, parm_path: str) -> Any:
    parm_tuple = session.hou.parmTuple(parm_path)
    if parm_tuple is not None:
        return parm_tuple
    parm = _get_parm(session, parm_path)
    parm_tuple = parm.tuple()
    if len(parm_tuple) <= 1:
        raise ValueError(f"Parameter is not a tuple: {parm_path}")
    return parm_tuple


def _tuple_members(parm: Any) -> list[Any]:
    return list(parm.tuple())


def _tuple_name(parm: Any) -> str:
    return localize(parm.tuple().name())


def _is_tuple_component(parm: Any) -> bool:
    members = _tuple_members(parm)
    return len(members) > 1 and localize(parm.name()) != _tuple_name(parm)


def _component_value(parm: Any) -> Any:
    data = localize(parm.valueAsData())
    members = _tuple_members(parm)
    if not (_is_tuple_component(parm) and isinstance(data, list) and len(data) == len(members)):
        return data
    names = [localize(item.name()) for item in members]
    return data[names.index(localize(parm.name()))]


def handle_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        return success_result({"parm_path": args.parm_path, "value": _component_value(parm)})


def handle_full(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        return success_result({"parm_path": args.parm_path, "value": localize(parm.asData(brief=False))})


def handle_menu(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        items = list(localize(parm.menuItems()))
        labels = list(localize(parm.menuLabels()))
        if not items:
            raise ValueError(f"Parameter does not provide a menu: {args.parm_path}")
        return success_result(
            {
                "parm_path": args.parm_path,
                "current_value": localize(parm.evalAsString()),
                "menu_items": [
                    {"token": token, "label": label}
                    for token, label in zip(items, labels, strict=True)
                ],
            }
        )


def handle_set(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        parm.set(_parse_cli_value(args.value))
        return success_result({"parm_path": args.parm_path, "applied": True})


def _parse_cli_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def handle_tuple_set(args: argparse.Namespace) -> dict:
    values = [_parse_cli_value(value) for value in args.values]
    with connect(args.host, args.port) as session:
        parm_tuple = _get_parm_tuple(session, args.parm_path)
        if len(values) != len(parm_tuple):
            raise ValueError(f"Tuple arity mismatch: expected {len(parm_tuple)} values, got {len(values)}")
        parm_tuple.set(values)
        return success_result({"parm_path": args.parm_path, "applied": True})


def _read_text_input(input_value: str) -> str:
    if input_value == "-":
        import sys

        return sys.stdin.read()
    with open(input_value, encoding="utf-8") as handle:
        return handle.read()


def _read_json_input(input_value: str) -> Any:
    import json

    if input_value == "-":
        return load_json_input("-")
    with open(input_value, encoding="utf-8") as handle:
        return json.load(handle)


def handle_text_set(args: argparse.Namespace) -> dict:
    text = _read_text_input(args.input)
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        parm.set(text)
        return success_result({"parm_path": args.parm_path, "applied": True})


def handle_full_set(args: argparse.Namespace) -> dict:
    payload = _read_json_input(args.input)
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        parm.setFromData(payload)
        return success_result({"parm_path": args.parm_path, "applied": True})


def _expression_language(session: Any, name: str) -> Any:
    return session.hou.exprLanguage.Python if name == "python" else session.hou.exprLanguage.Hscript


def handle_expression_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
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
    text = args.text if args.text is not None else _read_text_input(args.input)
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        parm.setExpression(text, _expression_language(session, args.language))
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
        parm = _get_parm(session, args.parm_path)
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


def _is_string_parm(session: Any, parm: Any) -> bool:
    return parm.parmTemplate().type() == session.hou.parmTemplateType.String


def handle_reference(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        target = _get_parm(session, args.target_parm)
        source = _get_parm(session, args.source_parm)
        function = "chs" if _is_string_parm(session, source) else "ch"
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


def _template_group_target(parm: Any, target: str) -> tuple[Any, Any, Any]:
    node = parm.node()
    if target == "definition":
        definition = node.type().definition()
        if definition is None:
            raise ValueError(f"Node type has no HDA definition: {localize(node.path())}")
        return node, definition, definition.parmTemplateGroup()
    return node, node, node.parmTemplateGroup()


def _template_summary(template: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": localize(template.name()),
        "label": localize(template.label()),
        "type": localize(template.type().name()),
        "components": int(localize(template.numComponents())),
        "help": localize(template.help()),
        "tags": localize(template.tags()),
        "join_with_next": bool(localize(template.joinWithNext())),
        "hidden": bool(localize(template.isHidden())),
        "label_hidden": bool(localize(template.isLabelHidden())),
    }
    for key, method in (
        ("default", "defaultValue"),
        ("min", "minValue"),
        ("max", "maxValue"),
        ("min_strict", "minIsStrict"),
        ("max_strict", "maxIsStrict"),
        ("menu_items", "menuItems"),
        ("menu_labels", "menuLabels"),
    ):
        if hasattr(template, method):
            result[key] = localize(getattr(template, method)())
    if hasattr(template, "conditionals"):
        result["conditionals"] = {
            localize(key.name()): localize(value)
            for key, value in template.conditionals().items()
        }
    return result


def handle_template_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        _node, _owner, group = _template_group_target(parm, args.target)
        template = group.find(localize(parm.tuple().name()))
        if template is None:
            raise ValueError(f"Parameter template not found: {args.parm_path}")
        return success_result(
            {
                "parm_path": args.parm_path,
                "target": args.target,
                "template": _template_summary(template),
            }
        )


def _menu_template(session: Any, old: Any, payload: dict[str, Any]) -> Any:
    items = tuple(payload["items"])
    labels = tuple(payload.get("labels", items))
    if len(items) != len(labels):
        raise ValueError("Menu items and labels must have the same length")
    current_default = old.defaultValue() if hasattr(old, "defaultValue") else 0
    default = payload.get("default", current_default)
    if isinstance(default, str) and default in items:
        default = items.index(default)
    template = session.hou.MenuParmTemplate(
        old.name(),
        payload.get("label", old.label()),
        items,
        labels,
        default_value=int(default),
    )
    template.setHelp(payload.get("help", old.help()))
    source_tags = payload.get("tags")
    if source_tags is None:
        source_tags = {
            str(localize(key)): str(localize(value))
            for key, value in old.tags().items()
        }
    if source_tags:
        template.setTags(_remote_dict(session, source_tags))
    template.setJoinWithNext(payload.get("join_with_next", old.joinWithNext()))
    return template


def _set_template_default(template: Any, value: Any) -> None:
    components = int(template.numComponents())
    if components > 1:
        values = value if isinstance(value, (list, tuple)) else [value] * components
        if len(values) != components:
            raise ValueError(f"Default arity mismatch: expected {components}, got {len(values)}")
        template.setDefaultValue(tuple(values))
        return
    type_name = localize(template.type().name())
    if type_name in {"Menu", "Toggle", "Ramp", "Folder"}:
        template.setDefaultValue(value)
    else:
        template.setDefaultValue((value,))


def _apply_template_patch(session: Any, old: Any, payload: dict[str, Any]) -> Any:
    requested_type = payload.get("type")
    if requested_type == "menu":
        return _menu_template(session, old, payload)
    if requested_type and requested_type.lower() != localize(old.type().name()).lower():
        raise ValueError("Only conversion to type 'menu' is currently supported")

    template = old.clone()
    if "label" in payload:
        template.setLabel(payload["label"])
    if "help" in payload:
        template.setHelp(payload["help"])
    if "tags" in payload:
        template.setTags(_remote_dict(session, payload["tags"]))
    if "join_with_next" in payload:
        template.setJoinWithNext(bool(payload["join_with_next"]))
    if "default" in payload:
        _set_template_default(template, payload["default"])
    for key, method in (
        ("min", "setMinValue"),
        ("max", "setMaxValue"),
        ("min_strict", "setMinIsStrict"),
        ("max_strict", "setMaxIsStrict"),
    ):
        if key in payload:
            if not hasattr(template, method):
                raise ValueError(f"Template does not support {key}")
            getattr(template, method)(payload[key])
    return template


def _remote_dict(session: Any, values: dict[str, Any]) -> Any:
    remote = session.connection.builtin.dict()
    for key, value in values.items():
        remote[str(key)] = str(value)
    return remote


def _apply_template_group(node: Any, owner: Any, group: Any, target: str) -> None:
    owner.setParmTemplateGroup(group)
    if target == "definition":
        owner.save(owner.libraryFilePath())
        node.matchCurrentDefinition()


def handle_template_set(args: argparse.Namespace) -> dict:
    payload = _read_json_input(args.input)
    if not isinstance(payload, dict):
        raise ValueError("Template patch must be a JSON object")
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        node, owner, group = _template_group_target(parm, args.target)
        template_name = localize(parm.tuple().name())
        old = group.find(template_name)
        if old is None:
            raise ValueError(f"Parameter template not found: {args.parm_path}")
        group.replace(template_name, _apply_template_patch(session, old, payload))
        _apply_template_group(node, owner, group, args.target)
        return success_result(
            {
                "parm_path": args.parm_path,
                "target": args.target,
                "template": _template_summary(group.find(template_name)),
                "applied": True,
            }
        )


def handle_default_set(args: argparse.Namespace) -> dict:
    value = None
    if not args.current:
        import json

        value = json.loads(args.value)
    with connect(args.host, args.port) as session:
        parm = _get_parm(session, args.parm_path)
        if args.current:
            members = list(parm.tuple())
            value = [localize(item.eval()) for item in members]
            if len(value) == 1:
                value = value[0]
        node, owner, group = _template_group_target(parm, args.target)
        template_name = localize(parm.tuple().name())
        template = group.find(template_name)
        if template is None:
            raise ValueError(f"Parameter template not found: {args.parm_path}")
        updated = template.clone()
        _set_template_default(updated, value)
        group.replace(template_name, updated)
        _apply_template_group(node, owner, group, args.target)
        return success_result(
            {
                "parm_path": args.parm_path,
                "target": args.target,
                "default": value,
                "applied": True,
            }
        )


SKIPPED_TEMPLATE_TYPES = {"Button", "Folder", "FolderSet", "Label", "Separator"}


def _get_node(session: Any, node_path: str) -> Any:
    node = session.hou.node(node_path)
    if node is None:
        raise ValueError(f"Node not found: {node_path}")
    return node


def _parm_template_type(parm: Any) -> str:
    return localize(parm.parmTemplate().type().name())


def _tuple_type_label(parm: Any) -> str:
    members = _tuple_members(parm)
    base = _parm_template_type(parm)
    return f"{base}{len(members)}" if len(members) > 1 else base


def _parm_flags(parm: Any) -> str:
    members = _tuple_members(parm)
    return "".join(["n" if any(not bool(localize(item.isAtDefault())) for item in members) else ""])


def _parm_display_name(parm: Any) -> str:
    members = _tuple_members(parm)
    return _tuple_name(parm) if len(members) > 1 else localize(parm.name())


def _parm_row_value(parm: Any) -> Any:
    members = _tuple_members(parm)
    data = localize(parm.valueAsData())
    return data if len(members) > 1 else data


def _parm_row(parm: Any) -> list[Any]:
    return [
        _parm_display_name(parm),
        _tuple_type_label(parm),
        _parm_row_value(parm),
        _parm_flags(parm),
    ]


def _iter_discoverable_parms(node: Any) -> list[Any]:
    rows: list[Any] = []
    seen: set[str] = set()
    for parm in node.parms():
        if _parm_template_type(parm) in SKIPPED_TEMPLATE_TYPES:
            continue
        key = localize(parm.path())
        members = _tuple_members(parm)
        if len(members) > 1:
            key = localize(members[0].path())
        if key in seen:
            continue
        seen.add(key)
        rows.append(parm)
    return rows


def _matches_parm(parm: Any, *, name: str | None, parm_type: str | None, non_default: bool) -> bool:
    if non_default and bool(localize(parm.isAtDefault())):
        members = _tuple_members(parm)
        if all(bool(localize(item.isAtDefault())) for item in members):
            return False
    if name:
        needle = name.lower()
        names = [_parm_display_name(parm), *[localize(item.name()) for item in _tuple_members(parm)]]
        lowered = [item.lower() for item in names]
        exact = any(item == needle for item in lowered)
        prefix = any(item.startswith(needle) for item in lowered)
        partial = len(needle) >= 3 and any(needle in item for item in lowered)
        if not (exact or prefix or partial):
            return False
    if parm_type and _tuple_type_label(parm) != parm_type:
        return False
    return True


def handle_node_parms_list(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = _get_node(session, args.node_path)
        rows = [
            _parm_row(parm)
            for parm in _iter_discoverable_parms(node)
            if _matches_parm(parm, name=None, parm_type=None, non_default=args.non_default)
        ][: args.max_parms]
        return success_result(
            {
                "node": args.node_path,
                "count": len(rows),
                "cols": ["p", "t", "v", "f"],
                "rows": rows,
            }
        )


def handle_node_parms_find(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = _get_node(session, args.node_path)
        rows = [
            _parm_row(parm)
            for parm in _iter_discoverable_parms(node)
            if _matches_parm(parm, name=args.name, parm_type=args.parm_type, non_default=args.non_default)
        ][: args.max_parms]
        return success_result(
            {
                "node": args.node_path,
                "query": {
                    key: value
                    for key, value in {
                        "name": args.name,
                        "type": args.parm_type,
                        "non_default": True if args.non_default else None,
                    }.items()
                    if value is not None
                },
                "count": len(rows),
                "cols": ["p", "t", "v", "f"],
                "rows": rows,
            }
        )
