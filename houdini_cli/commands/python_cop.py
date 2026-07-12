"""Python COP binding, signature, control, and connection helpers."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize

CONTROL_TYPES = {"string", "int", "float", "float2", "float3", "float4", "ramp"}
GENERATED_FOLDER = "folder_generatedparms_pythoncode"
_VDB_TYPES = {"any": "fnvdb", "float": "fvdb", "vector": "vvdb", "int": "ivdb", "floatn": "fnvdb"}


def scalar(binding: Any, key: str) -> Any:
    return localize(binding[key])


def require_python_cop(node: Any) -> Any:
    category = str(localize(node.type().category().name())).lower()
    code = node.parm("pythoncode")
    if category != "cop" or code is None or node.parm("bindings") is None:
        raise ValueError(f"Node is not a supported Python COP: {localize(node.path())}")
    return code


def extract_bindings(session: Any, node: Any) -> list[Any]:
    code = require_python_cop(node).evalAsString()
    return list(session.hou.text.oclExtractBindings(code))


def signature_type(binding: Any, *, output: bool) -> str:
    kind = str(scalar(binding, "type"))
    if kind == "layer":
        value = str(scalar(binding, "layertype"))
        return "floatn" if value == "float?" else value
    if kind in {"attribute", "volume", "geo"}:
        return "geo"
    if kind == "vdb":
        return _VDB_TYPES[str(scalar(binding, "vdbtype"))]
    if not output and kind == "metadata":
        return "metadata"
    raise ValueError(f"Unsupported Python COP port binding type: {kind}")


def desired_ports(bindings: list[Any], *, output: bool) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], int] = {}
    for binding in bindings:
        kind = str(scalar(binding, "type"))
        readable = bool(scalar(binding, "readable"))
        writeable = bool(scalar(binding, "writeable"))
        optional = bool(scalar(binding, "optional"))
        if output:
            if not writeable:
                continue
        elif kind == "layer" and not readable and not writeable:
            entries.append({"name": str(scalar(binding, "name")), "type": "metadata", "optional": optional})
            continue
        elif not readable:
            continue
        if kind == "layer":
            entry = {"name": str(scalar(binding, "portname") or scalar(binding, "name")), "type": signature_type(binding, output=output)}
            if not output:
                entry["optional"] = optional
            entries.append(entry)
            continue
        if kind not in {"attribute", "volume", "vdb", "geo"}:
            continue
        name = str(scalar(binding, "portname") or scalar(binding, "name"))
        port_type = signature_type(binding, output=output)
        key = (name, port_type)
        if key not in grouped:
            grouped[key] = len(entries)
            entry = {"name": name, "type": port_type}
            if not output:
                entry["optional"] = optional
            entries.append(entry)
        else:
            entries[grouped[key]]["optional"] = bool(entries[grouped[key]]["optional"]) and optional
    return entries


def desired_binding_rows(bindings: list[Any]) -> list[dict[str, str]]:
    return [
        {"name": str(scalar(binding, "name")), "type": str(scalar(binding, "type"))}
        for binding in bindings
        if str(scalar(binding, "type")) in CONTROL_TYPES
    ]


def current_ports(node: Any, *, output: bool) -> list[dict[str, Any]]:
    prefix = "output" if output else "input"
    count = int(node.parm("outputs" if output else "inputs").eval())
    rows = []
    for index in range(1, count + 1):
        row = {
            "name": str(node.parm(f"{prefix}{index}_name").evalAsString()),
            "type": str(node.parm(f"{prefix}{index}_type").evalAsString() or "floatn"),
        }
        if not output:
            row["optional"] = bool(node.parm(f"input{index}_optional").eval())
        rows.append(row)
    return rows


def current_binding_rows(node: Any) -> list[dict[str, str]]:
    return [
        {
            "name": str(node.parm(f"bindings{index}_name").evalAsString()),
            "type": str(node.parm(f"bindings{index}_type").evalAsString()),
        }
        for index in range(1, int(node.parm("bindings").eval()) + 1)
    ]


def generated_controls(node: Any) -> list[str]:
    folder = node.parmTemplateGroup().find(GENERATED_FOLDER)
    if folder is None:
        return []
    return [str(localize(template.name())) for template in folder.parmTemplates()]


def control_rows(node: Any, bindings: list[Any]) -> list[dict[str, Any]]:
    generated = set(generated_controls(node))
    rows = []
    binding_index = 0
    for binding in bindings:
        kind = str(scalar(binding, "type"))
        if kind not in CONTROL_TYPES:
            continue
        binding_index += 1
        base = str(scalar(binding, "name"))
        control = node.parm(base) or node.parmTuple(base) or node.parm(f"{base}_val") or node.parmTuple(f"{base}_val")
        name = str(localize(control.name())) if control is not None else None
        suffix = {
            "string": "sval", "int": "intval", "float": "fval",
            "float2": "v2val1", "float3": "v3val1", "float4": "v4val1",
        }.get(kind)
        if kind == "ramp":
            suffix = "ramp_rgb" if str(scalar(binding, "ramptype")) == "vector" else "ramp"
        link = node.parm(f"bindings{binding_index}_{suffix}") if suffix else None
        linked = False
        if control is not None and link is not None:
            try:
                raw = str(localize(link.rawValue()))
                linked = any(token in raw for token in (f'"./{name}', f"'./{name}", f'"{name}"', f"'{name}'"))
            except Exception:
                linked = False
        rows.append({"binding": base, "type": kind, "control": name, "generated": name in generated if name else False, "missing": control is None, "linked": linked})
    return rows


def capture_spare_state(node: Any) -> dict[str, dict[str, Any]]:
    states = {}
    for parm in node.spareParms():
        template_type = str(localize(parm.parmTemplate().type().name()))
        if template_type in {"Folder", "FolderSet", "Button", "Label", "Separator"}:
            continue
        name = str(localize(parm.name()))
        state: dict[str, Any] = {}
        try:
            state["expression"] = parm.expression()
            state["language"] = parm.expressionLanguage()
        except Exception:
            try:
                state["value"] = localize(parm.eval())
            except Exception:
                continue
        states[name] = state
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


def capture_connections(node: Any) -> list[dict[str, Any]]:
    ports = current_ports(node, output=False)
    rows = []
    for connection in node.inputConnections():
        index = int(connection.inputIndex())
        source = connection.inputNode()
        if source is None or not 0 <= index < len(ports):
            continue
        rows.append({"name": ports[index]["name"], "from_path": str(localize(source.path())), "from_output_index": int(connection.outputIndex()), "source_node": source})
    return rows


def _disconnect_all(node: Any) -> None:
    for connection in list(node.inputConnections()):
        node.setInput(int(connection.inputIndex()), None)


def restore_connections(node: Any, ports: list[dict[str, Any]], captured: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indices: dict[str, list[int]] = {}
    for index, port in enumerate(ports):
        indices.setdefault(str(port["name"]), []).append(index)
    _disconnect_all(node)
    used: dict[str, int] = {}
    restored, dropped = [], []
    for row in captured:
        name = str(row["name"])
        occurrence = used.get(name, 0)
        used[name] = occurrence + 1
        choices = indices.get(name, [])
        public = {key: value for key, value in row.items() if key != "source_node"}
        if occurrence >= len(choices):
            dropped.append(public)
            continue
        to_index = choices[occurrence]
        node.setInput(to_index, row["source_node"], int(row["from_output_index"]))
        restored.append({**public, "to_input_index": to_index})
    return restored, dropped


def prune_generated_controls(node: Any, desired_names: set[str]) -> list[str]:
    group = node.parmTemplateGroup()
    folder = group.find(GENERATED_FOLDER)
    if folder is None:
        return []
    removed = []
    updated = folder.clone()
    kept = []
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


def validation(node: Any, bindings: list[Any]) -> dict[str, Any]:
    desired_inputs = desired_ports(bindings, output=False)
    desired_outputs = desired_ports(bindings, output=True)
    desired_rows = desired_binding_rows(bindings)
    current_inputs = current_ports(node, output=False)
    current_outputs = current_ports(node, output=True)
    current_rows = current_binding_rows(node)
    controls = control_rows(node, bindings)
    missing_controls = [row["binding"] for row in controls if row["missing"]]
    unlinked_controls = [row["binding"] for row in controls if not row["missing"] and not row["linked"]]
    generated = generated_controls(node)
    desired_names = {row["name"] for row in desired_rows}
    stale_generated = [name for name in generated if name not in desired_names and not (name.endswith("_val") and name[:-4] in desired_names)]
    signature_matches = current_inputs == desired_inputs and current_outputs == desired_outputs
    bindings_match = current_rows == desired_rows
    hints = []
    if not signature_matches:
        hints.append(f"Python COP signature differs from #bind directives. Try: houdini-cli python sync {localize(node.path())}")
    if not bindings_match:
        hints.append(f"Python COP binding rows differ from #bind directives. Try: houdini-cli python sync {localize(node.path())}")
    if stale_generated:
        hints.append("Stale generated controls: " + ", ".join(stale_generated) + ". Use --prune-generated to remove them.")
    if unlinked_controls:
        hints.append("Binding rows are not linked to controls: " + ", ".join(unlinked_controls) + ".")
    ok = signature_matches and bindings_match and not missing_controls and not unlinked_controls and not stale_generated
    return {
        "node_path": localize(node.path()), "context": "cop", "binding_count": len(bindings),
        "signature_matches_code": signature_matches, "bindings_match_code": bindings_match,
        "sync_required": not ok, "ok": ok,
        "desired_inputs": desired_inputs, "desired_outputs": desired_outputs, "desired_bindings": desired_rows,
        "current_inputs": current_inputs, "current_outputs": current_outputs, "current_bindings": current_rows,
        "controls": controls, "generated_controls": generated, "missing_controls": missing_controls,
        "unlinked_controls": unlinked_controls, "stale_generated_controls": stale_generated, "hints": hints,
    }


def sync(session: Any, node: Any, bindings: list[Any], *, bindings_only: bool, prune_generated: bool, preserve_values: bool) -> dict[str, Any]:
    state = capture_spare_state(node) if preserve_values else {}
    connections = capture_connections(node) if not bindings_only else []
    existing_input_count = int(node.parm("inputs").eval())
    existing_output_count = int(node.parm("outputs").eval())
    if bindings_only:
        node.parm("bindings").set(0)
    else:
        node.parm("inputs").set(0)
        node.parm("outputs").set(0)
        node.parm("bindings").set(0)
    session.connection.modules.vexpressionmenu.createSpareParmsFromOCLBindings(node, "pythoncode")
    if bindings_only:
        node.parm("inputs").set(existing_input_count)
        node.parm("outputs").set(existing_output_count)
    desired_names = {row["name"] for row in desired_binding_rows(bindings)}
    removed = prune_generated_controls(node, desired_names) if prune_generated else []
    restored_values = restore_spare_state(node, state) if state else []
    restored_connections: list[dict[str, Any]] = []
    dropped_connections: list[dict[str, Any]] = []
    if not bindings_only:
        restored_connections, dropped_connections = restore_connections(node, current_ports(node, output=False), connections)
    return {
        "removed_generated_controls": removed, "restored_controls": restored_values,
        "restored_connections": restored_connections, "dropped_connections": dropped_connections,
    }
