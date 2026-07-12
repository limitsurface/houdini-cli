"""Python Snippet SOP binding and control synchronization."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize

CONTROL_TYPES = {"string", "int", "float", "float2", "float3", "float4", "ramp"}
GENERATED_FOLDER = "folder_generatedparms_pythoncode"


def scalar(binding: Any, key: str) -> Any:
    return localize(binding[key])


def require_python_sop(node: Any) -> Any:
    category = str(localize(node.type().category().name())).lower()
    type_name = str(localize(node.type().name()))
    code = node.parm("pythoncode")
    if category != "sop" or type_name != "pythonsnippet" or code is None or node.parm("bindings") is None:
        raise ValueError(f"Node is not a supported Python Snippet SOP: {localize(node.path())}")
    return code


def extract_bindings(session: Any, node: Any) -> list[Any]:
    return list(session.hou.text.oclExtractBindings(require_python_sop(node).evalAsString()))


def desired_binding_rows(bindings: list[Any]) -> list[dict[str, str]]:
    return [
        {"name": str(scalar(binding, "name")), "type": str(scalar(binding, "type"))}
        for binding in bindings
        if str(scalar(binding, "type")) in CONTROL_TYPES
    ]


def current_binding_rows(node: Any) -> list[dict[str, str]]:
    return [
        {"name": str(node.parm(f"bindings{i}_name").evalAsString()), "type": str(node.parm(f"bindings{i}_type").evalAsString())}
        for i in range(1, int(node.parm("bindings").eval()) + 1)
    ]


def generated_controls(node: Any) -> list[str]:
    folder = node.parmTemplateGroup().find(GENERATED_FOLDER)
    return [] if folder is None else [str(localize(template.name())) for template in folder.parmTemplates()]


def _control(node: Any, name: str) -> Any:
    return node.parm(name) or node.parmTuple(name) or node.parm(f"{name}_val") or node.parmTuple(f"{name}_val")


def control_rows(node: Any, bindings: list[Any]) -> list[dict[str, Any]]:
    generated = set(generated_controls(node))
    rows = []
    row_index = 0
    for binding in bindings:
        kind = str(scalar(binding, "type"))
        if kind not in CONTROL_TYPES:
            continue
        row_index += 1
        base = str(scalar(binding, "name"))
        control = _control(node, base)
        name = str(localize(control.name())) if control is not None else None
        suffix = {"string": "sval", "int": "intval", "float": "fval", "float2": "v2val1", "float3": "v3val1", "float4": "v4val1"}.get(kind)
        if kind == "ramp":
            suffix = "ramp_rgb" if str(scalar(binding, "ramptype")) == "vector" else "ramp"
        link = node.parm(f"bindings{row_index}_{suffix}") if suffix else None
        linked = False
        if control is not None and link is not None:
            try:
                raw = str(localize(link.rawValue()))
                linked = any(token in raw for token in (f'"./{name}', f"'./{name}", f'"{name}"', f"'{name}'"))
            except Exception:
                pass
        rows.append({"binding": base, "type": kind, "control": name, "generated": name in generated if name else False, "missing": control is None, "linked": linked})
    return rows


def capture_spare_state(node: Any) -> dict[str, dict[str, Any]]:
    states = {}
    for parm in node.spareParms():
        if str(localize(parm.parmTemplate().type().name())) in {"Folder", "FolderSet", "Button", "Label", "Separator"}:
            continue
        state: dict[str, Any] = {}
        try:
            state["expression"] = parm.expression()
            state["language"] = parm.expressionLanguage()
        except Exception:
            try:
                state["value"] = localize(parm.eval())
            except Exception:
                continue
        states[str(localize(parm.name()))] = state
    return states


def restore_spare_state(node: Any, states: dict[str, dict[str, Any]]) -> list[str]:
    restored = []
    for name, state in states.items():
        parm = node.parm(name)
        if parm is None:
            continue
        if "expression" in state:
            try:
                parm.setExpression(state["expression"], state.get("language"))
            except TypeError:
                parm.setExpression(state["expression"])
        elif "value" in state:
            parm.set(state["value"])
        restored.append(name)
    return restored


def prune_generated_controls(node: Any, desired_names: set[str]) -> list[str]:
    group = node.parmTemplateGroup()
    folder = group.find(GENERATED_FOLDER)
    if folder is None:
        return []
    removed, kept = [], []
    updated = folder.clone()
    for template in updated.parmTemplates():
        name = str(localize(template.name()))
        if name not in desired_names and not (name.endswith("_val") and name[:-4] in desired_names):
            removed.append(name)
        else:
            kept.append(template)
    if removed:
        updated.setParmTemplates(tuple(kept))
        group.replace(GENERATED_FOLDER, updated)
        node.setParmTemplateGroup(group)
    return removed


def remove_incompatible_controls(node: Any, bindings: list[Any]) -> list[str]:
    generated = set(generated_controls(node))
    incompatible_generated = []
    incompatible_external = []
    for binding in bindings:
        kind = str(scalar(binding, "type"))
        if kind not in CONTROL_TYPES:
            continue
        name = str(scalar(binding, "name"))
        control = _control(node, name)
        if control is None:
            continue
        template = control.parmTemplate()
        actual_type = str(localize(template.type().name()))
        expected_type = "String" if kind == "string" else "Int" if kind == "int" else "Ramp" if kind == "ramp" else "Float"
        compatible = actual_type == expected_type
        if compatible and kind.startswith("float"):
            expected_size = {"float": 1, "float2": 2, "float3": 3, "float4": 4}[kind]
            compatible = int(localize(template.numComponents())) == expected_size
        if compatible and kind == "ramp":
            expected_ramp = "Color" if str(scalar(binding, "ramptype")) == "vector" else "Float"
            compatible = str(localize(template.parmType().name())) == expected_ramp
        if not compatible:
            (incompatible_generated if name in generated else incompatible_external).append(name)
    if incompatible_external:
        raise ValueError(
            "Externally organized Python SOP controls have incompatible types: "
            + ", ".join(incompatible_external)
        )
    if not incompatible_generated:
        return []
    group = node.parmTemplateGroup()
    folder = group.find(GENERATED_FOLDER)
    updated = folder.clone()
    updated.setParmTemplates(tuple(t for t in updated.parmTemplates() if str(localize(t.name())) not in incompatible_generated))
    group.replace(GENERATED_FOLDER, updated)
    node.setParmTemplateGroup(group)
    return incompatible_generated


def validation(node: Any, bindings: list[Any]) -> dict[str, Any]:
    desired = desired_binding_rows(bindings)
    current = current_binding_rows(node)
    controls = control_rows(node, bindings)
    missing = [row["binding"] for row in controls if row["missing"]]
    unlinked = [row["binding"] for row in controls if not row["missing"] and not row["linked"]]
    generated = generated_controls(node)
    desired_names = {row["name"] for row in desired}
    stale = [name for name in generated if name not in desired_names and not (name.endswith("_val") and name[:-4] in desired_names)]
    rows_match = current == desired
    hints = []
    if not rows_match:
        hints.append(f"Python SOP binding rows differ from #bind directives. Try: houdini-cli python sync {localize(node.path())}")
    if missing:
        hints.append("Missing controls: " + ", ".join(missing) + ".")
    if unlinked:
        hints.append("Binding rows are not linked to controls: " + ", ".join(unlinked) + ".")
    if stale:
        hints.append("Stale generated controls: " + ", ".join(stale) + ". Use --prune-generated to remove them.")
    ok = rows_match and not missing and not unlinked and not stale
    return {
        "node_path": localize(node.path()), "context": "sop", "binding_count": len(bindings),
        "bindings_match_code": rows_match, "sync_required": not ok, "ok": ok,
        "desired_bindings": desired, "current_bindings": current, "controls": controls,
        "generated_controls": generated, "missing_controls": missing, "unlinked_controls": unlinked,
        "stale_generated_controls": stale, "hints": hints,
    }


def sync(session: Any, node: Any, bindings: list[Any], *, prune_generated: bool, preserve_values: bool) -> dict[str, Any]:
    state = capture_spare_state(node) if preserve_values else {}
    replaced = remove_incompatible_controls(node, bindings)
    for name in replaced:
        state.pop(name, None)
    node.parm("bindings").set(0)
    session.connection.modules.vexpressionmenu.createSpareParmsFromOCLBindings(node, "pythoncode")
    desired_names = {row["name"] for row in desired_binding_rows(bindings)}
    removed = prune_generated_controls(node, desired_names) if prune_generated else []
    restored = restore_spare_state(node, state) if state else []
    return {"removed_generated_controls": removed, "replaced_generated_controls": replaced, "restored_controls": restored, "restored_connections": [], "dropped_connections": []}
