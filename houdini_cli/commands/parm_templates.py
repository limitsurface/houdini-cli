"""Parameter template and default commands."""

from __future__ import annotations

import argparse
import json
from typing import Any

from ..format.envelopes import success_result
from ..remote.parm_templates import PARM_TEMPLATE_REMOTE
from ..transport.rpyc import connect, localize
from ..util.input import read_json_input
from .parm_common import get_parm


def template_group_target(parm: Any, target: str) -> tuple[Any, Any, Any]:
    node = parm.node()
    if target == "definition":
        definition = node.type().definition()
        if definition is None:
            raise ValueError(f"Node type has no HDA definition: {localize(node.path())}")
        return node, definition, definition.parmTemplateGroup()
    return node, node, node.parmTemplateGroup()


def template_summary(template: Any) -> dict[str, Any]:
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
        parm = get_parm(session, args.parm_path)
        _node, _owner, group = template_group_target(parm, args.target)
        template = group.find(localize(parm.tuple().name()))
        if template is None:
            raise ValueError(f"Parameter template not found: {args.parm_path}")
        return success_result(
            {
                "parm_path": args.parm_path,
                "target": args.target,
                "template": template_summary(template),
            }
        )


def menu_template(session: Any, old: Any, payload: dict[str, Any]) -> Any:
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
        template.setTags(remote_dict(session, source_tags))
    template.setJoinWithNext(payload.get("join_with_next", old.joinWithNext()))
    return template


def set_template_default(template: Any, value: Any) -> None:
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


def apply_template_patch(session: Any, old: Any, payload: dict[str, Any]) -> Any:
    requested_type = payload.get("type")
    if requested_type == "menu":
        return menu_template(session, old, payload)
    if requested_type and requested_type.lower() != localize(old.type().name()).lower():
        raise ValueError("Only conversion to type 'menu' is currently supported")

    template = old.clone()
    if "label" in payload:
        template.setLabel(payload["label"])
    if "help" in payload:
        template.setHelp(payload["help"])
    if "tags" in payload:
        template.setTags(remote_dict(session, payload["tags"]))
    if "join_with_next" in payload:
        template.setJoinWithNext(bool(payload["join_with_next"]))
    if "default" in payload:
        set_template_default(template, payload["default"])
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


def remote_dict(session: Any, values: dict[str, Any]) -> Any:
    remote = session.connection.builtin.dict()
    for key, value in values.items():
        remote[str(key)] = str(value)
    return remote


def apply_template_group(node: Any, owner: Any, group: Any, target: str) -> None:
    owner.setParmTemplateGroup(group)
    if target == "definition":
        owner.save(owner.libraryFilePath())
        node.matchCurrentDefinition()


def set_definition_default_in_houdini(session: Any, parm_path: str, value: Any) -> dict[str, Any]:
    connection = getattr(session, "connection", None)
    if not callable(getattr(connection, "execute", None)) or not callable(getattr(connection, "eval", None)):
        raise ValueError("Definition default updates require a Houdini remote connection")
    return localize(PARM_TEMPLATE_REMOTE.evaluate(connection, "set_definition_default", parm_path, value))


def handle_template_set(args: argparse.Namespace) -> dict:
    payload = read_json_input(args.input)
    if not isinstance(payload, dict):
        raise ValueError("Template patch must be a JSON object")
    with connect(args.host, args.port) as session:
        parm = get_parm(session, args.parm_path)
        node, owner, group = template_group_target(parm, args.target)
        template_name = localize(parm.tuple().name())
        old = group.find(template_name)
        if old is None:
            raise ValueError(f"Parameter template not found: {args.parm_path}")
        group.replace(template_name, apply_template_patch(session, old, payload))
        apply_template_group(node, owner, group, args.target)
        return success_result(
            {
                "parm_path": args.parm_path,
                "target": args.target,
                "template": template_summary(group.find(template_name)),
                "applied": True,
            }
        )


def handle_default_set(args: argparse.Namespace) -> dict:
    value = None
    if not args.current:
        value = json.loads(args.value)
    with connect(args.host, args.port) as session:
        if args.target == "definition" and not args.current:
            result = set_definition_default_in_houdini(
                session, args.parm_path, value
            )
            return success_result(
                {
                    "parm_path": args.parm_path,
                    "target": args.target,
                    "default": result["default"],
                    "library": result["library"],
                    "applied": True,
                }
            )
        parm = get_parm(session, args.parm_path)
        if args.current:
            members = list(parm.tuple())
            value = [localize(item.eval()) for item in members]
            if len(value) == 1:
                value = value[0]
        node, owner, group = template_group_target(parm, args.target)
        template_name = localize(parm.tuple().name())
        template = group.find(template_name)
        if template is None:
            raise ValueError(f"Parameter template not found: {args.parm_path}")
        updated = template.clone()
        set_template_default(updated, value)
        group.replace(template_name, updated)
        apply_template_group(node, owner, group, args.target)
        return success_result(
            {
                "parm_path": args.parm_path,
                "target": args.target,
                "default": value,
                "applied": True,
            }
        )
