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
"""

NODE_PARMS_REMOTE = RemoteModule(
    namespace="node_parms",
    source=SOURCE,
    entrypoints={"rows": "_houdini_cli_parm_rows"},
)
