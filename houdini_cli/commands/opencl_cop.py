"""OpenCL COP signature and validation helpers."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize
from ..remote.opencl_cop import OPENCL_COP_REMOTE
from .opencl_bindings import (
    SPARE_PARM_BINDING_TYPES,
    binding_scalar,
    data_scalar,
    node_messages,
    safe_cook,
    sync_bindings,
)
from .opencl_spares import parm_bindings, sync_spare_parms_preserving_values


_VDB_SIGNATURE_TYPES = {
    "any": "fnvdb",
    "float": "fvdb",
    "vector": "vvdb",
    "int": "ivdb",
    "floatn": "fnvdb",
}


def signature_type(binding_type: str, binding: Any, *, output: bool) -> str:
    if binding_type == "layer":
        return str(binding_scalar(binding, "layertype"))
    if binding_type in {"attribute", "volume"}:
        return "geo"
    if binding_type == "vdb":
        return _VDB_SIGNATURE_TYPES[str(binding_scalar(binding, "vdbtype"))]
    if not output and binding_type == "metadata":
        return "metadata"
    raise ValueError(f"Unsupported binding type for OpenCL signature sync: {binding_type}")


def port_signature_entries(bindings: list[Any], *, output: bool) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    grouped_indices: dict[tuple[str, str], int] = {}

    for binding in bindings:
        binding_type = str(binding_scalar(binding, "type"))
        readable = bool(binding_scalar(binding, "readable"))
        writeable = bool(binding_scalar(binding, "writeable"))
        optional = bool(binding_scalar(binding, "optional"))

        if output:
            if not writeable:
                continue
        else:
            if binding_type == "layer" and not readable and not writeable:
                entries.append(
                    {
                        "name": str(binding_scalar(binding, "name")),
                        "type": "metadata",
                        "optional": optional,
                        "precision": str(binding_scalar(binding, "precision")),
                    }
                )
                continue
            if not readable:
                continue

        if binding_type == "layer":
            entries.append(
                {
                    "name": str(binding_scalar(binding, "name")),
                    "type": signature_type(binding_type, binding, output=output),
                    "optional": optional,
                    "precision": str(binding_scalar(binding, "precision")),
                }
            )
            continue

        if binding_type not in {"attribute", "volume", "vdb"}:
            continue

        portname = str(binding_scalar(binding, "portname"))
        resolved_type = signature_type(binding_type, binding, output=output)
        key = (resolved_type, portname)
        existing_index = grouped_indices.get(key)
        if existing_index is None:
            grouped_indices[key] = len(entries)
            entries.append(
                {
                    "name": portname,
                    "type": resolved_type,
                    "optional": optional,
                    "precision": str(binding_scalar(binding, "precision")),
                }
            )
        else:
            entries[existing_index]["optional"] = bool(entries[existing_index]["optional"]) and optional

    return entries


def existing_signature_entries(opencl_node: Any, *, output: bool) -> list[dict[str, Any]]:
    count_parm = opencl_node.parm("outputs" if output else "inputs")
    if count_parm is not None:
        try:
            count = int(count_parm.eval())
        except Exception:
            count = 0
        result = []
        for index in range(1, count + 1):
            prefix = "output" if output else "input"
            name_parm = opencl_node.parm(f"{prefix}{index}_name")
            type_parm = opencl_node.parm(f"{prefix}{index}_type")
            if name_parm is None or type_parm is None:
                continue
            try:
                name = str(name_parm.evalAsString())
                signature_type = str(type_parm.evalAsString() or "floatn")
            except Exception:
                continue
            if not name:
                continue
            entry: dict[str, Any] = {
                "name": name,
                "type": signature_type,
                "optional": False,
            }
            if not output:
                optional_parm = opencl_node.parm(f"input{index}_optional")
                try:
                    entry["optional"] = bool(optional_parm.eval()) if optional_parm is not None else False
                except Exception:
                    entry["optional"] = False
            result.append(entry)
        return result

    try:
        data = localize(opencl_node.parmsAsData(brief=False))
    except Exception:
        return []

    section_name = "outputs" if output else "inputs"
    entries = data.get(section_name)
    if not isinstance(entries, list):
        return []

    name_key = "output#_name" if output else "input#_name"
    type_key = "output#_type" if output else "input#_type"
    optional_key = "input#_optional"

    result: list[dict[str, Any]] = []
    for row in entries:
        if not isinstance(row, dict):
            continue
        name = data_scalar(row.get(name_key))
        if not name:
            continue
        entry: dict[str, Any] = {
            "name": str(name),
            "type": str(data_scalar(row.get(type_key)) or "floatn"),
            "optional": bool(data_scalar(row.get(optional_key, False))) if not output else False,
        }
        result.append(entry)
    return result


def signature_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (str(entry["name"]), str(entry["type"]))


def validation_output_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": entry["name"],
            "type": entry["type"],
            "optional": bool(entry.get("optional", False)),
        }
        for entry in entries
    ]


def preserve_signature_order(existing: list[dict[str, Any]], desired: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not existing or not desired:
        return desired

    remaining: dict[tuple[str, str], list[dict[str, Any]]] = {}
    desired_order: list[tuple[str, str]] = []
    for entry in desired:
        key = signature_key(entry)
        remaining.setdefault(key, []).append(entry)
        desired_order.append(key)

    preserved: list[dict[str, Any]] = []
    for entry in existing:
        key = signature_key(entry)
        bucket = remaining.get(key)
        if bucket:
            preserved.append(bucket.pop(0))
            if not bucket:
                remaining.pop(key, None)

    for key in desired_order:
        bucket = remaining.get(key)
        if bucket:
            preserved.extend(bucket)
            remaining.pop(key, None)

    return preserved


def summary_signature_entries(opencl_node: Any, *, output: bool) -> list[dict[str, Any]]:
    entries = existing_signature_entries(opencl_node, output=output)
    if output:
        return [{"name": entry["name"], "type": entry["type"]} for entry in entries]
    return [{"name": entry["name"], "type": entry["type"], "optional": entry["optional"]} for entry in entries]


def input_data_types(opencl_node: Any) -> list[str]:
    try:
        return [str(localize(value)) for value in opencl_node.inputDataTypes()]
    except Exception:
        return []


def output_data_types(node: Any) -> list[str]:
    try:
        return [str(localize(value)) for value in node.outputDataTypes()]
    except Exception:
        return []


def current_input_connections(opencl_node: Any) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    try:
        connections = list(opencl_node.inputConnections())
    except Exception:
        return result

    for connection in connections:
        source_node = connection.inputNode()
        output_index = int(connection.outputIndex())
        source_types = output_data_types(source_node) if source_node is not None else []
        source_output_type = source_types[output_index] if 0 <= output_index < len(source_types) else None
        result[int(connection.inputIndex())] = {
            "from_path": str(localize(source_node.path())) if source_node is not None else None,
            "from_output_index": output_index,
            "from_output_name": str(localize(connection.outputName())),
            "source_output_type": source_output_type,
        }
    return result


def parm_expression(parm: Any) -> str | None:
    if parm is None:
        return None
    try:
        return str(parm.expression())
    except Exception:
        return None


def binding_value_parm_names(index: int, binding_type: str) -> list[tuple[str, tuple[str, ...]]]:
    prefix = f"bindings{index}_"
    if binding_type == "int":
        return [(f"{prefix}intval", ("",))]
    if binding_type == "float":
        return [(f"{prefix}fval", ("",))]
    if binding_type == "float2":
        return [(f"{prefix}v2val{component}", (str(component), "xy"[component - 1])) for component in range(1, 3)]
    if binding_type == "float3":
        return [(f"{prefix}v3val{component}", (str(component), "xyz"[component - 1])) for component in range(1, 4)]
    if binding_type == "float4":
        return [(f"{prefix}v4val{component}", (str(component), "xyzw"[component - 1])) for component in range(1, 5)]
    return []


def binding_row_hints(opencl_node: Any) -> list[str]:
    bindings_parm = opencl_node.parm("bindings")
    if bindings_parm is None:
        return []

    try:
        binding_count = int(bindings_parm.eval())
    except Exception:
        return []

    hints: list[str] = []
    layer_rows: list[str] = []
    static_rows: list[str] = []

    for index in range(1, binding_count + 1):
        name_parm = opencl_node.parm(f"bindings{index}_name")
        type_parm = opencl_node.parm(f"bindings{index}_type")
        if name_parm is None or type_parm is None:
            continue

        try:
            name = str(name_parm.evalAsString())
            binding_type = str(type_parm.evalAsString())
        except Exception:
            continue

        if binding_type == "layer":
            layer_rows.append(name)
            continue

        if binding_type not in SPARE_PARM_BINDING_TYPES:
            continue

        expected = f'ch("./{name}")'
        for parm_name, component_suffixes in binding_value_parm_names(index, binding_type):
            expr = parm_expression(opencl_node.parm(parm_name))
            expected_exprs = {
                expected if not component_suffix else f'ch("./{name}{component_suffix}")'
                for component_suffix in component_suffixes
            }
            if expr not in expected_exprs:
                static_rows.append(name)
                break

    if layer_rows:
        hints.append(
            "OpenCL binding rows include layer bindings "
            f"({', '.join(layer_rows)}); layer bindings should live in Signature inputs/outputs. "
            "Try: houdini-cli opencl sync <node-path>"
        )
    if static_rows:
        hints.append(
            "OpenCL parm binding rows are not linked to generated spare parms "
            f"({', '.join(static_rows)}); UI changes may not affect the kernel. "
            "Try: houdini-cli opencl sync <node-path>"
        )

    return hints

def disconnect_input(opencl_node: Any, index: int) -> None:
    try:
        opencl_node.setInput(index, None)
    except TypeError:
        opencl_node.setInput(index, None, 0)



def cop_validation_summary(
    opencl_node: Any,
    *,
    bindings: list[Any],
    runover: str,
    current_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if current_state is None:
        safe_cook(opencl_node)
    desired_inputs = port_signature_entries(bindings, output=False)
    desired_outputs = port_signature_entries(bindings, output=True)
    if current_state is None:
        current_inputs = summary_signature_entries(opencl_node, output=False)
        current_outputs = summary_signature_entries(opencl_node, output=True)
        input_types = input_data_types(opencl_node)
        connections = current_input_connections(opencl_node)
        messages = node_messages(opencl_node)
        hints = binding_row_hints(opencl_node)
    else:
        current_inputs = current_state["current_inputs"]
        current_outputs = current_state["current_outputs"]
        input_types = current_state["input_types"]
        connections = {int(key): value for key, value in current_state["connections"].items()}
        messages = {
            "errors": current_state["errors"],
            "warnings": current_state["warnings"],
            "messages": current_state["messages"],
        }
        hints = list(current_state["hints"])

    input_rows: list[dict[str, Any]] = []
    invalid_connection_count = 0
    missing_required_count = 0

    for index, entry in enumerate(current_inputs):
        expected_data_type = input_types[index] if index < len(input_types) else None
        connected = connections.get(index)
        compatible = None
        if connected is None:
            compatible = bool(entry["optional"])
            if not entry["optional"]:
                missing_required_count += 1
        elif expected_data_type is not None and connected["source_output_type"] is not None:
            compatible = connected["source_output_type"] == expected_data_type
            if not compatible:
                invalid_connection_count += 1
        elif connected is not None:
            compatible = False
            invalid_connection_count += 1

        row = {
            "index": index,
            "name": str(entry["name"]),
            "type": str(entry["type"]),
            "expected_data_type": expected_data_type,
            "optional": bool(entry["optional"]),
            "connected": connected is not None,
            "compatible": compatible,
        }
        if connected is not None:
            row.update(connected)
        input_rows.append(row)

    desired_input_rows = [{"name": entry["name"], "type": entry["type"], "optional": entry["optional"]} for entry in desired_inputs]
    desired_output_rows = validation_output_rows(desired_outputs)
    current_output_rows = validation_output_rows(current_outputs)
    signature_matches_kernel = current_inputs == desired_input_rows and current_output_rows == desired_output_rows
    if not signature_matches_kernel:
        hints.append(f"OpenCL signature differs from kernel #bind directives. Try: houdini-cli opencl sync {localize(opencl_node.path())}")

    return {
        "node_path": localize(opencl_node.path()),
        "context": "cop",
        "runover": runover,
        "binding_count": len(bindings),
        "signature_matches_kernel": signature_matches_kernel,
        "sync_required": not signature_matches_kernel,
        "invalid_connection_count": invalid_connection_count,
        "missing_required_count": missing_required_count,
        "ok": signature_matches_kernel and invalid_connection_count == 0 and missing_required_count == 0 and not messages["errors"],
        "desired_inputs": desired_input_rows,
        "desired_outputs": desired_output_rows,
        "current_inputs": current_inputs,
        "current_outputs": current_output_rows,
        "inputs": input_rows,
        "hints": hints,
        **messages,
    }

def sync_signature(
    opencl_node: Any,
    input_entries: list[dict[str, Any]],
    output_entries: list[dict[str, Any]],
) -> None:
    opencl_node.setParms({"inputs": 0, "outputs": 0})
    opencl_node.setParms({"inputs": len(input_entries), "outputs": len(output_entries)})

    parm_values: dict[str, Any] = {}

    for index, entry in enumerate(input_entries, start=1):
        parm_values[f"input{index}_name"] = str(entry["name"])
        parm_values[f"input{index}_type"] = str(entry["type"])
        parm_values[f"input{index}_optional"] = bool(entry["optional"])

    for index, entry in enumerate(output_entries, start=1):
        parm_values[f"output{index}_name"] = str(entry["name"])
        parm_values[f"output{index}_type"] = str(entry["type"])
        parm_values[f"output{index}_metadata"] = "first"
        parm_values[f"output{index}_precision"] = str(entry["precision"])
        parm_values[f"output{index}_typeinfo"] = "node"
        parm_values[f"output{index}_metaname"] = ""

    if parm_values:
        opencl_node.setParms(parm_values)




def cop_validation_state_in_houdini(session: Any, node_path: str) -> dict[str, Any] | None:
    connection = getattr(session, "connection", None)
    if not callable(getattr(connection, "execute", None)) or not callable(getattr(connection, "eval", None)):
        return None
    return localize(OPENCL_COP_REMOTE.evaluate(connection, "state", node_path))


def apply_cop_signature(
    session: Any,
    opencl_node: Any,
    bindings: list[Any],
    *,
    clear: bool,
    bindings_only: bool,
    preserve_spare_values: bool = False,
) -> dict[str, Any]:
    input_entries = port_signature_entries(bindings, output=False)
    output_entries = port_signature_entries(bindings, output=True)

    if not bindings_only and not clear:
        input_entries = preserve_signature_order(
            existing_signature_entries(opencl_node, output=False),
            input_entries,
        )
        output_entries = preserve_signature_order(
            existing_signature_entries(opencl_node, output=True),
            output_entries,
        )

    if clear:
        if bindings_only:
            opencl_node.setParms({"bindings": 0})
        else:
            opencl_node.setParms({"inputs": 0, "outputs": 0, "bindings": 0})

    spare_bindings = parm_bindings(bindings)
    spare_parms = sync_spare_parms_preserving_values(
        session,
        opencl_node,
        spare_bindings,
        preserve=preserve_spare_values,
    )

    sync_bindings(opencl_node, spare_bindings)
    if not bindings_only:
        sync_signature(opencl_node, input_entries, output_entries)

    return {
        "inputs": (
            summary_signature_entries(opencl_node, output=False)
            if bindings_only
            else [{"name": entry["name"], "type": entry["type"], "optional": entry["optional"]} for entry in input_entries]
        ),
        "outputs": (
            summary_signature_entries(opencl_node, output=True)
            if bindings_only
            else [{"name": entry["name"], "type": entry["type"]} for entry in output_entries]
        ),
        "spare_parms": spare_parms,
    }
