"""Remote operations for node parameter discovery."""

from __future__ import annotations

from .module import RemoteModule


SOURCE = r"""
import hou

SKIPPED_TEMPLATE_TYPES = {"Button", "Folder", "FolderSet", "Label", "Separator"}

def _houdini_cli_parm_rows(node_path, name, parm_type, non_default, full_values, max_parms):
    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)

    needle = name.lower() if name else None
    rows = []
    seen = set()
    for parm in node.parms():
        template = parm.parmTemplate()
        template_type = template.type().name()
        if template_type in SKIPPED_TEMPLATE_TYPES:
            continue

        members = list(parm.tuple())
        display_name = parm.tuple().name() if len(members) > 1 else parm.name()
        key = members[0].path() if len(members) > 1 else parm.path()
        if key in seen:
            continue
        seen.add(key)

        tuple_type = "{}{}".format(template_type, len(members)) if len(members) > 1 else template_type
        if parm_type and tuple_type != parm_type:
            continue

        is_default = all(item.isAtDefault() for item in members)
        if non_default and is_default:
            continue
        flag = "" if is_default else "n"

        if needle:
            names = [display_name] + [item.name() for item in members]
            lowered = [item.lower() for item in names]
            exact = any(item == needle for item in lowered)
            prefix = any(item.startswith(needle) for item in lowered)
            partial = len(needle) >= 3 and any(needle in item for item in lowered)
            if not (exact or prefix or partial):
                continue

        value = parm.valueAsData()
        if not full_values and isinstance(value, str) and len(value) > 120:
            value = value[:117] + "..."

        rows.append([display_name, tuple_type, value, flag])
        if len(rows) >= max_parms:
            break
    return rows

def _houdini_cli_expression_summary(parm, max_items):
    rows = []
    total = 0
    for member in parm.tuple():
        try:
            keyframes = member.keyframes()
        except Exception:
            keyframes = ()
        if not keyframes:
            continue
        total += 1
        if len(rows) >= max_items:
            continue
        try:
            text = member.expression()
        except Exception:
            text = None
        try:
            language = str(member.expressionLanguage()).rsplit(".", 1)[-1]
        except Exception:
            language = None
        rows.append({"parm": member.name(), "language": language, "text": text})
    return {"count": total, "items": rows, "truncated": total > len(rows)}

def _houdini_cli_ramp_summary(parm, max_items):
    ramp = parm.eval()
    keys = list(ramp.keys())
    bases = [str(item).rsplit(".", 1)[-1].lower() for item in ramp.basis()]
    unique_bases = list(dict.fromkeys(bases))
    return {
        "kind": "ramp",
        "point_count": len(keys),
        "basis": unique_bases[:max_items],
        "basis_truncated": len(unique_bases) > max_items,
    }

def _houdini_cli_bounded_value(parm, template_type, mode, max_items):
    if mode == "none":
        return None
    if mode == "full":
        return parm.valueAsData()
    if template_type == "Ramp":
        return _houdini_cli_ramp_summary(parm, max_items)
    try:
        instances = list(parm.multiParmInstances())
    except Exception:
        instances = []
    if instances:
        return {"kind": "multiparm", "instance_count": len(instances)}
    value = parm.valueAsData()
    if isinstance(value, str):
        if mode == "scalar" and len(value) <= 120:
            return value
        preview_limit = min(120, max_items * 20)
        return {
            "kind": "string",
            "length": len(value),
            "preview": value[:preview_limit],
            "truncated": len(value) > preview_limit,
        }
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        if mode == "scalar" and len(value) <= 4:
            return value
        return {
            "kind": "sequence",
            "item_count": len(value),
            "items": list(value[:max_items]),
            "truncated": len(value) > max_items,
        }
    if isinstance(value, dict):
        keys = list(value.keys())
        return {
            "kind": "mapping",
            "item_count": len(keys),
            "keys": keys[:max_items],
            "truncated": len(keys) > max_items,
        }
    return {"kind": template_type.lower(), "type": type(value).__name__}

def _houdini_cli_bounded_parm_rows(node_path, name, parm_type, non_default, value_mode, max_parms, max_items):
    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)
    needle = name.lower() if name else None
    rows = []
    total = 0
    seen = set()
    for parm in node.parms():
        template = parm.parmTemplate()
        template_type = template.type().name()
        if template_type in SKIPPED_TEMPLATE_TYPES:
            continue
        members = list(parm.tuple())
        display_name = parm.tuple().name() if len(members) > 1 else parm.name()
        key = members[0].path() if len(members) > 1 else parm.path()
        if key in seen:
            continue
        seen.add(key)
        tuple_type = "{}{}".format(template_type, len(members)) if len(members) > 1 else template_type
        if parm_type and tuple_type != parm_type:
            continue
        is_default = all(item.isAtDefault() for item in members)
        if non_default and is_default:
            continue
        if needle:
            names = [display_name] + [item.name() for item in members]
            lowered = [item.lower() for item in names]
            if not (
                any(item == needle for item in lowered)
                or any(item.startswith(needle) for item in lowered)
                or (len(needle) >= 3 and any(needle in item for item in lowered))
            ):
                continue
        total += 1
        if len(rows) >= max_parms:
            continue
        value = _houdini_cli_bounded_value(parm, template_type, value_mode, max_items)
        if value_mode != "none":
            expressions = _houdini_cli_expression_summary(parm, max_items)
            if expressions["count"]:
                if isinstance(value, dict):
                    value = dict(value)
                    value["expressions"] = expressions
                else:
                    value = {"kind": "evaluated_expression", "value": value, "expressions": expressions}
        rows.append([display_name, tuple_type, value, "" if is_default else "n"])
    return {"rows": rows, "total": total, "truncated": total > len(rows)}

def _houdini_cli_project_parms(node_path, requested_names, value_mode, max_items):
    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)
    items = []
    missing = []
    for requested_name in requested_names:
        parm = node.parm(requested_name)
        if parm is None:
            parm_tuple = node.parmTuple(requested_name)
            if parm_tuple is not None and len(parm_tuple):
                parm = parm_tuple[0]
        if parm is None:
            missing.append(requested_name)
            continue
        members = list(parm.tuple())
        template_type = parm.parmTemplate().type().name()
        tuple_type = "{}{}".format(template_type, len(members)) if len(members) > 1 else template_type
        value = _houdini_cli_bounded_value(parm, template_type, value_mode, max_items)
        item = {
            "p": requested_name,
            "t": tuple_type,
            "v": value,
            "default": all(member.isAtDefault() for member in members),
        }
        expressions = _houdini_cli_expression_summary(parm, max_items)
        if expressions["count"]:
            item["expressions"] = expressions
        items.append(item)
    return {"items": items, "missing": missing}
"""

NODE_PARMS_REMOTE = RemoteModule(
    namespace="node_parms",
    source=SOURCE,
    entrypoints={
        "rows": "_houdini_cli_parm_rows",
        "bounded_rows": "_houdini_cli_bounded_parm_rows",
        "project": "_houdini_cli_project_parms",
    },
)
