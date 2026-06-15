"""OpenCL commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .node_common import get_node

_VDB_SIGNATURE_TYPES = {
    "any": "fnvdb",
    "float": "fvdb",
    "vector": "vvdb",
    "int": "ivdb",
    "floatn": "fnvdb",
}

_SPARE_PARM_BINDING_TYPES = {"int", "float", "float2", "float3", "float4"}
_DOP_SPARE_PARM_BINDING_TYPES = {"int", "float", "float3", "float4"}


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    opencl_parser = subparsers.add_parser("opencl", help="Inspect and synchronize OpenCL nodes.")
    opencl_subparsers = opencl_parser.add_subparsers(dest="opencl_command", required=True)

    validate_parser = opencl_subparsers.add_parser(
        "validate",
        help="Validate OpenCL COP signatures, SOP bindings, or DOP parameters against a kernel.",
    )
    validate_parser.add_argument("node_path", help="OpenCL node path.")
    validate_parser.add_argument(
        "--details",
        action="store_true",
        help="Return full desired/current signatures, connections, hints, and messages.",
    )
    validate_parser.set_defaults(handler=handle_validate)

    sync_parser = opencl_subparsers.add_parser(
        "sync",
        help="Synchronize OpenCL COP, SOP, or DOP interfaces from #bind directives.",
    )
    sync_parser.add_argument("node_path", help="OpenCL node path.")
    sync_parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing signature and bindings before rebuilding.",
    )
    sync_parser.add_argument(
        "--bindings-only",
        action="store_true",
        help="For COPs, avoid changing visible inputs/outputs; SOPs and DOPs always sync their binding rows.",
    )
    sync_parser.add_argument(
        "--disconnect-invalid",
        action="store_true",
        help="After syncing, disconnect any wired inputs whose source output type no longer matches the regenerated input type.",
    )
    sync_parser.add_argument(
        "--details",
        action="store_true",
        help="Include the full post-sync validation payload.",
    )
    sync_parser.set_defaults(handler=handle_sync)


def _binding_scalar(binding: Any, key: str) -> Any:
    return localize(binding[key])


def _binding_vector(binding: Any, key: str, size: int) -> list[float]:
    value = binding[key]
    return [float(value[index]) for index in range(size)]


def _signature_type(binding_type: str, binding: Any, *, output: bool) -> str:
    if binding_type == "layer":
        return str(_binding_scalar(binding, "layertype"))
    if binding_type in {"attribute", "volume"}:
        return "geo"
    if binding_type == "vdb":
        return _VDB_SIGNATURE_TYPES[str(_binding_scalar(binding, "vdbtype"))]
    if not output and binding_type == "metadata":
        return "metadata"
    raise ValueError(f"Unsupported binding type for OpenCL signature sync: {binding_type}")


def _binding_parm_values(index: int, binding: Any) -> dict[str, Any]:
    prefix = f"bindings{index}_"
    binding_type = str(_binding_scalar(binding, "type"))
    values: dict[str, Any] = {
        f"{prefix}name": str(_binding_scalar(binding, "name")),
        f"{prefix}type": binding_type,
        f"{prefix}portname": str(_binding_scalar(binding, "portname")),
        f"{prefix}precision": str(_binding_scalar(binding, "precision")),
        f"{prefix}optional": bool(_binding_scalar(binding, "optional")),
        f"{prefix}defval": bool(_binding_scalar(binding, "defval")),
        f"{prefix}readable": bool(_binding_scalar(binding, "readable")),
        f"{prefix}writeable": bool(_binding_scalar(binding, "writeable")),
        f"{prefix}timescale": str(_binding_scalar(binding, "timescale")),
    }

    if binding_type == "layer":
        values[f"{prefix}layertype"] = str(_binding_scalar(binding, "layertype"))
        values[f"{prefix}layerborder"] = str(_binding_scalar(binding, "layerborder"))
    elif binding_type == "attribute":
        values[f"{prefix}attribute"] = str(_binding_scalar(binding, "attribute"))
        values[f"{prefix}attribclass"] = str(_binding_scalar(binding, "attribclass"))
        values[f"{prefix}attribtype"] = str(_binding_scalar(binding, "attribtype"))
        values[f"{prefix}attribsize"] = int(_binding_scalar(binding, "attribsize"))
    elif binding_type == "volume":
        values[f"{prefix}volume"] = str(_binding_scalar(binding, "volume"))
        values[f"{prefix}resolution"] = bool(_binding_scalar(binding, "resolution"))
        values[f"{prefix}voxelsize"] = bool(_binding_scalar(binding, "voxelsize"))
        values[f"{prefix}xformtoworld"] = bool(_binding_scalar(binding, "xformtoworld"))
        values[f"{prefix}xformtovoxel"] = bool(_binding_scalar(binding, "xformtovoxel"))
    elif binding_type == "vdb":
        values[f"{prefix}volume"] = str(_binding_scalar(binding, "volume"))
        values[f"{prefix}vdbtype"] = str(_binding_scalar(binding, "vdbtype"))
    elif binding_type == "int":
        values[f"{prefix}intval"] = int(_binding_scalar(binding, "intval"))
    elif binding_type == "float":
        values[f"{prefix}fval"] = float(_binding_scalar(binding, "fval"))
    elif binding_type == "float2":
        values[f"{prefix}v2val"] = _binding_vector(binding, "v2val", 2)
    elif binding_type == "float3":
        values[f"{prefix}v3val"] = _binding_vector(binding, "v3val", 3)
    elif binding_type == "float4":
        values[f"{prefix}v4val"] = _binding_vector(binding, "v4val", 4)

    return values


def _spare_parm_name(binding: Any) -> str:
    return str(_binding_scalar(binding, "name"))


def _spare_parm_label(binding: Any) -> str:
    name = _spare_parm_name(binding)
    return name.replace("_", " ").title()


def _spare_parm_template(session: Any, binding: Any) -> Any:
    binding_type = str(_binding_scalar(binding, "type"))
    name = _spare_parm_name(binding)
    label = _spare_parm_label(binding)

    if binding_type == "int":
        return session.hou.IntParmTemplate(
            name,
            label,
            1,
            default_value=(int(_binding_scalar(binding, "intval")),),
        )
    if binding_type == "float":
        return session.hou.FloatParmTemplate(
            name,
            label,
            1,
            default_value=(float(_binding_scalar(binding, "fval")),),
        )
    if binding_type == "float2":
        return session.hou.FloatParmTemplate(
            name,
            label,
            2,
            default_value=tuple(_binding_vector(binding, "v2val", 2)),
        )
    if binding_type == "float3":
        return session.hou.FloatParmTemplate(
            name,
            label,
            3,
            default_value=tuple(_binding_vector(binding, "v3val", 3)),
        )
    if binding_type == "float4":
        return session.hou.FloatParmTemplate(
            name,
            label,
            4,
            default_value=tuple(_binding_vector(binding, "v4val", 4)),
        )
    raise ValueError(f"Unsupported spare parm binding type: {binding_type}")


def _generated_spare_parm_folder(session: Any, bindings: list[Any]) -> Any:
    folder = session.hou.FolderParmTemplate(
        "folder_generatedparms_kernelcode",
        "Generated Channel Parameters",
    )
    for binding in bindings:
        folder.addParmTemplate(_spare_parm_template(session, binding))
    return folder


def _remove_generated_spare_parm_ui(opencl_node: Any) -> None:
    group = opencl_node.parmTemplateGroup()
    changed = False

    for folder_name in ("opencl_sync_controls", "folder_generatedparms_kernelcode"):
        entries = getattr(group, "entries", lambda: ())()
        if any(entry.name() == folder_name for entry in entries):
            group.remove(folder_name)
            changed = True
            continue

        try:
            group.remove(folder_name)
            changed = True
        except Exception:
            pass

    if changed:
        opencl_node.setParmTemplateGroup(group)


def _manual_sync_spare_parms(session: Any, opencl_node: Any, bindings: list[Any]) -> list[str]:
    group = opencl_node.parmTemplateGroup()
    generated_folder = _generated_spare_parm_folder(session, bindings)

    try:
        group.insertBefore("kernelcode", generated_folder)
    except Exception:
        group.append(generated_folder)

    opencl_node.setParmTemplateGroup(group)
    return [_spare_parm_name(binding) for binding in bindings]


def _sync_spare_parms(session: Any, opencl_node: Any, bindings: list[Any]) -> list[str]:
    desired_bindings = [
        binding
        for binding in bindings
        if str(_binding_scalar(binding, "type")) in _SPARE_PARM_BINDING_TYPES
    ]
    _remove_generated_spare_parm_ui(opencl_node)

    if not desired_bindings:
        return []

    return _manual_sync_spare_parms(session, opencl_node, desired_bindings)


def _parm_bindings(bindings: list[Any]) -> list[Any]:
    return [
        binding
        for binding in bindings
        if str(_binding_scalar(binding, "type")) in _SPARE_PARM_BINDING_TYPES
    ]


def _binding_row_values(bindings: list[Any]) -> dict[str, Any]:
    parm_values: dict[str, Any] = {}
    for index, binding in enumerate(bindings, start=1):
        parm_values.update(_binding_parm_values(index, binding))
    return parm_values


def _node_category(opencl_node: Any) -> str:
    try:
        return str(localize(opencl_node.type().category().name()))
    except Exception:
        return ""


def _is_sop_opencl(opencl_node: Any) -> bool:
    return _node_category(opencl_node).lower() == "sop"


def _is_dop_opencl(opencl_node: Any) -> bool:
    return _node_category(opencl_node).lower() == "dop"


def _opencl_context(opencl_node: Any) -> str:
    if _is_sop_opencl(opencl_node):
        return "sop"
    if _is_dop_opencl(opencl_node):
        return "dop"
    return "cop"


def _set_binding_value_expression(opencl_node: Any, parm_name: str, expression: str) -> None:
    parm = opencl_node.parm(parm_name)
    if parm is None:
        return
    parm.setExpression(expression)


def _link_binding_value_parms(opencl_node: Any, bindings: list[Any]) -> None:
    for index, binding in enumerate(bindings, start=1):
        binding_type = str(_binding_scalar(binding, "type"))
        spare_name = _spare_parm_name(binding)
        expression = f'ch("./{spare_name}")'
        prefix = f"bindings{index}_"

        if binding_type == "int":
            _set_binding_value_expression(opencl_node, f"{prefix}intval", expression)
        elif binding_type == "float":
            _set_binding_value_expression(opencl_node, f"{prefix}fval", expression)
        elif binding_type == "float2":
            for component in range(1, 3):
                _set_binding_value_expression(opencl_node, f"{prefix}v2val{component}", f'ch("./{spare_name}{component}")')
        elif binding_type == "float3":
            for component in range(1, 4):
                _set_binding_value_expression(opencl_node, f"{prefix}v3val{component}", f'ch("./{spare_name}{component}")')
        elif binding_type == "float4":
            for component in range(1, 5):
                _set_binding_value_expression(opencl_node, f"{prefix}v4val{component}", f'ch("./{spare_name}{component}")')


def _port_signature_entries(bindings: list[Any], *, output: bool) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    grouped_indices: dict[tuple[str, str], int] = {}

    for binding in bindings:
        binding_type = str(_binding_scalar(binding, "type"))
        readable = bool(_binding_scalar(binding, "readable"))
        writeable = bool(_binding_scalar(binding, "writeable"))
        optional = bool(_binding_scalar(binding, "optional"))

        if output:
            if not writeable:
                continue
        else:
            if binding_type == "layer" and not readable and not writeable:
                entries.append(
                    {
                        "name": str(_binding_scalar(binding, "name")),
                        "type": "metadata",
                        "optional": optional,
                        "precision": str(_binding_scalar(binding, "precision")),
                    }
                )
                continue
            if not readable:
                continue

        if binding_type == "layer":
            entries.append(
                {
                    "name": str(_binding_scalar(binding, "name")),
                    "type": _signature_type(binding_type, binding, output=output),
                    "optional": optional,
                    "precision": str(_binding_scalar(binding, "precision")),
                }
            )
            continue

        if binding_type not in {"attribute", "volume", "vdb"}:
            continue

        portname = str(_binding_scalar(binding, "portname"))
        signature_type = _signature_type(binding_type, binding, output=output)
        key = (signature_type, portname)
        existing_index = grouped_indices.get(key)
        if existing_index is None:
            grouped_indices[key] = len(entries)
            entries.append(
                {
                    "name": portname,
                    "type": signature_type,
                    "optional": optional,
                    "precision": str(_binding_scalar(binding, "precision")),
                }
            )
        else:
            entries[existing_index]["optional"] = bool(entries[existing_index]["optional"]) and optional

    return entries


def _existing_signature_entries(opencl_node: Any, *, output: bool) -> list[dict[str, Any]]:
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
        name = _data_scalar(row.get(name_key))
        if not name:
            continue
        entry: dict[str, Any] = {
            "name": str(name),
            "type": str(_data_scalar(row.get(type_key)) or "floatn"),
            "optional": bool(_data_scalar(row.get(optional_key, False))) if not output else False,
        }
        result.append(entry)
    return result


def _data_scalar(value: Any) -> Any:
    while isinstance(value, dict) and "value" in value:
        value = value["value"]
    return value


def _compact_binding_rows(bindings: list[Any]) -> list[list[Any]]:
    rows = []
    for binding in bindings:
        binding_type = str(_binding_scalar(binding, "type"))
        readable = bool(_binding_scalar(binding, "readable"))
        writeable = bool(_binding_scalar(binding, "writeable"))
        if binding_type in _SPARE_PARM_BINDING_TYPES:
            direction = "parm"
        elif readable and writeable:
            direction = "inout"
        elif writeable:
            direction = "output"
        else:
            direction = "input"
        rows.append([_spare_parm_name(binding), binding_type, direction])
    return rows


def _compact_validation(validation: dict[str, Any], bindings: list[Any]) -> dict[str, Any]:
    result = {
        "node_path": validation["node_path"],
        "context": validation.get("context", "cop"),
        "runover": validation.get("runover", ""),
        "binding_count": validation["binding_count"],
        "binding_cols": ["name", "type", "direction"],
        "bindings": _compact_binding_rows(bindings),
        "clean": bool(validation["ok"]),
        "sync_required": bool(validation.get("sync_required", False)),
        "invalid_connection_count": validation.get("invalid_connection_count", 0),
        "missing_required_count": validation.get("missing_required_count", 0),
    }
    for key in ("errors", "warnings", "messages", "hints"):
        if validation.get(key):
            result[key] = validation[key]
    return result


def _signature_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (str(entry["name"]), str(entry["type"]))


def _preserve_signature_order(existing: list[dict[str, Any]], desired: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not existing or not desired:
        return desired

    remaining: dict[tuple[str, str], list[dict[str, Any]]] = {}
    desired_order: list[tuple[str, str]] = []
    for entry in desired:
        key = _signature_key(entry)
        remaining.setdefault(key, []).append(entry)
        desired_order.append(key)

    preserved: list[dict[str, Any]] = []
    for entry in existing:
        key = _signature_key(entry)
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


def _summary_signature_entries(opencl_node: Any, *, output: bool) -> list[dict[str, Any]]:
    entries = _existing_signature_entries(opencl_node, output=output)
    if output:
        return [{"name": entry["name"], "type": entry["type"]} for entry in entries]
    return [{"name": entry["name"], "type": entry["type"], "optional": entry["optional"]} for entry in entries]


def _node_messages(opencl_node: Any) -> dict[str, list[str]]:
    data: dict[str, list[str]] = {}
    for key in ("errors", "warnings", "messages"):
        values = getattr(opencl_node, key, None)
        if callable(values):
            try:
                data[key] = [str(localize(value)) for value in values()]
            except Exception:
                data[key] = []
        else:
            data[key] = []
    return data


def _input_data_types(opencl_node: Any) -> list[str]:
    try:
        return [str(localize(value)) for value in opencl_node.inputDataTypes()]
    except Exception:
        return []


def _output_data_types(node: Any) -> list[str]:
    try:
        return [str(localize(value)) for value in node.outputDataTypes()]
    except Exception:
        return []


def _current_input_connections(opencl_node: Any) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    try:
        connections = list(opencl_node.inputConnections())
    except Exception:
        return result

    for connection in connections:
        source_node = connection.inputNode()
        output_index = int(connection.outputIndex())
        source_types = _output_data_types(source_node) if source_node is not None else []
        source_output_type = source_types[output_index] if 0 <= output_index < len(source_types) else None
        result[int(connection.inputIndex())] = {
            "from_path": str(localize(source_node.path())) if source_node is not None else None,
            "from_output_index": output_index,
            "from_output_name": str(localize(connection.outputName())),
            "source_output_type": source_output_type,
        }
    return result


def _parm_expression(parm: Any) -> str | None:
    if parm is None:
        return None
    try:
        return str(parm.expression())
    except Exception:
        return None


def _binding_value_parm_names(index: int, binding_type: str) -> list[tuple[str, tuple[str, ...]]]:
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


def _binding_row_hints(opencl_node: Any) -> list[str]:
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

        if binding_type not in _SPARE_PARM_BINDING_TYPES:
            continue

        expected = f'ch("./{name}")'
        for parm_name, component_suffixes in _binding_value_parm_names(index, binding_type):
            expr = _parm_expression(opencl_node.parm(parm_name))
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


def _binding_row_summary(opencl_node: Any) -> list[dict[str, Any]]:
    bindings_parm = opencl_node.parm("bindings")
    if bindings_parm is None:
        return []
    try:
        binding_count = int(bindings_parm.eval())
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for index in range(1, binding_count + 1):
        name_parm = opencl_node.parm(f"bindings{index}_name")
        type_parm = opencl_node.parm(f"bindings{index}_type")
        if name_parm is None or type_parm is None:
            continue
        try:
            rows.append(
                {
                    "name": str(name_parm.evalAsString()),
                    "type": str(type_parm.evalAsString()),
                }
            )
        except Exception:
            continue
    return rows


def _desired_binding_row_summary(bindings: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": str(_binding_scalar(binding, "name")),
            "type": str(_binding_scalar(binding, "type")),
        }
        for binding in bindings
    ]


def _dop_binding_parm_values(index: int, binding: Any) -> dict[str, Any]:
    prefix = f"parameter{index}"
    binding_type = str(_binding_scalar(binding, "type"))
    values: dict[str, Any] = {
        f"{prefix}Name": str(_binding_scalar(binding, "name")),
        f"{prefix}Type": binding_type,
        f"{prefix}Precision": str(_binding_scalar(binding, "precision")),
        f"{prefix}Input": bool(_binding_scalar(binding, "readable")),
        f"{prefix}Output": bool(_binding_scalar(binding, "writeable")),
        f"{prefix}Optional": bool(_binding_scalar(binding, "optional")),
        f"{prefix}DefVal": bool(_binding_scalar(binding, "defval")),
        f"{prefix}TimeScale": str(_binding_scalar(binding, "timescale")),
    }

    if binding_type in {"scalarfield", "vectorfield", "matrixfield"}:
        values[f"{prefix}Field"] = str(_binding_scalar(binding, "fieldname"))
        values[f"{prefix}Offsets"] = bool(_binding_scalar(binding, "fieldoffsets"))
    elif binding_type == "attribute":
        values[f"{prefix}Geometry"] = str(_binding_scalar(binding, "geometry"))
        values[f"{prefix}Attribute"] = str(_binding_scalar(binding, "attribute"))
        values[f"{prefix}Class"] = str(_binding_scalar(binding, "attribclass"))
        values[f"{prefix}AttributeType"] = str(_binding_scalar(binding, "attribtype"))
        values[f"{prefix}AttributeSize"] = int(_binding_scalar(binding, "attribsize"))
    elif binding_type == "volume":
        values[f"{prefix}Geometry"] = str(_binding_scalar(binding, "geometry"))
        values[f"{prefix}Volume"] = str(_binding_scalar(binding, "volume"))
        values[f"{prefix}Resolution"] = bool(_binding_scalar(binding, "resolution"))
        values[f"{prefix}VoxelSize"] = bool(_binding_scalar(binding, "voxelsize"))
        values[f"{prefix}XformToWorld"] = bool(_binding_scalar(binding, "xformtoworld"))
        values[f"{prefix}XformToVoxel"] = bool(_binding_scalar(binding, "xformtovoxel"))
    elif binding_type == "vdb":
        values[f"{prefix}Geometry"] = str(_binding_scalar(binding, "geometry"))
        values[f"{prefix}Volume"] = str(_binding_scalar(binding, "volume"))
        values[f"{prefix}VDBType"] = str(_binding_scalar(binding, "vdbtype"))
    elif binding_type == "option":
        values[f"{prefix}DataName"] = str(_binding_scalar(binding, "dataname"))
        values[f"{prefix}OptionName"] = str(_binding_scalar(binding, "optionname"))
        values[f"{prefix}OptionType"] = str(_binding_scalar(binding, "optiontype"))
        values[f"{prefix}OptionSize"] = int(_binding_scalar(binding, "optionsize"))
    elif binding_type == "ramp":
        values[f"{prefix}RampSize"] = int(_binding_scalar(binding, "rampsize"))
    elif binding_type == "int":
        values[f"{prefix}Int"] = int(_binding_scalar(binding, "intval"))
    elif binding_type == "float":
        values[f"{prefix}Flt"] = float(_binding_scalar(binding, "fval"))
    elif binding_type == "float3":
        values[f"{prefix}Flt3"] = _binding_vector(binding, "v3val", 3)
    elif binding_type == "float4":
        values[f"{prefix}Flt4"] = _binding_vector(binding, "v4val", 4)
    else:
        raise ValueError(f"Unsupported Gas OpenCL binding type: {binding_type}")

    return values


def _dop_binding_row_summary(opencl_node: Any) -> list[dict[str, Any]]:
    count_parm = opencl_node.parm("paramcount")
    if count_parm is None:
        return []
    try:
        count = int(count_parm.eval())
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        name_parm = opencl_node.parm(f"parameter{index}Name")
        type_parm = opencl_node.parm(f"parameter{index}Type")
        if name_parm is None or type_parm is None:
            continue
        rows.append(
            {
                "name": str(name_parm.evalAsString()),
                "type": str(type_parm.evalAsString()),
            }
        )
    return rows


def _link_dop_binding_value_parms(opencl_node: Any, bindings: list[Any]) -> None:
    suffixes = {
        "int": ["Int"],
        "float": ["Flt"],
        "float3": ["Flt31", "Flt32", "Flt33"],
        "float4": ["Flt41", "Flt42", "Flt43", "Flt44"],
    }
    for index, binding in enumerate(bindings, start=1):
        binding_type = str(_binding_scalar(binding, "type"))
        spare_name = _spare_parm_name(binding)
        for component, suffix in enumerate(suffixes.get(binding_type, []), start=1):
            target = f"parameter{index}{suffix}"
            source = spare_name if len(suffixes[binding_type]) == 1 else f"{spare_name}{component}"
            _set_binding_value_expression(opencl_node, target, f'ch("./{source}")')


def _sync_dop_bindings(opencl_node: Any, bindings: list[Any]) -> None:
    opencl_node.setParms({"paramcount": 0})
    if not bindings:
        return
    opencl_node.setParms({"paramcount": len(bindings)})
    parm_values: dict[str, Any] = {}
    for index, binding in enumerate(bindings, start=1):
        parm_values.update(_dop_binding_parm_values(index, binding))
    parm_values = {
        name: value
        for name, value in parm_values.items()
        if opencl_node.parm(name) is not None
    }
    opencl_node.setParms(parm_values)
    _link_dop_binding_value_parms(opencl_node, bindings)


def _disconnect_input(opencl_node: Any, index: int) -> None:
    try:
        opencl_node.setInput(index, None)
    except TypeError:
        opencl_node.setInput(index, None, 0)


def _safe_cook(node: Any) -> None:
    cook = getattr(node, "cook", None)
    if not callable(cook):
        return
    try:
        cook(force=True)
    except TypeError:
        cook()
    except Exception:
        return


def _validation_summary(
    opencl_node: Any,
    *,
    bindings: list[Any],
    runover: str,
) -> dict[str, Any]:
    _safe_cook(opencl_node)
    if _is_dop_opencl(opencl_node):
        desired_rows = _desired_binding_row_summary(bindings)
        current_rows = _dop_binding_row_summary(opencl_node)
        bindings_match_kernel = current_rows == desired_rows
        messages = _node_messages(opencl_node)
        hints: list[str] = []
        if not bindings_match_kernel:
            hints.append(
                f"Gas OpenCL parameter rows differ from kernel #bind directives. "
                f"Try: houdini-cli opencl sync {localize(opencl_node.path())}"
            )
        return {
            "node_path": localize(opencl_node.path()),
            "context": "dop",
            "runover": runover,
            "binding_count": len(bindings),
            "bindings_match_kernel": bindings_match_kernel,
            "signature_matches_kernel": None,
            "sync_required": not bindings_match_kernel,
            "invalid_connection_count": 0,
            "missing_required_count": 0,
            "ok": bindings_match_kernel and not messages["errors"],
            "desired_bindings": desired_rows,
            "current_bindings": current_rows,
            "desired_inputs": [],
            "desired_outputs": [],
            "current_inputs": [],
            "current_outputs": [],
            "inputs": [],
            "hints": hints,
            **messages,
        }

    if _is_sop_opencl(opencl_node):
        desired_rows = _desired_binding_row_summary(bindings)
        current_rows = _binding_row_summary(opencl_node)
        bindings_match_kernel = current_rows == desired_rows
        messages = _node_messages(opencl_node)
        hints: list[str] = []
        if not bindings_match_kernel:
            hints.append(
                f"OpenCL SOP binding rows differ from kernel #bind directives. "
                f"Try: houdini-cli opencl sync {localize(opencl_node.path())}"
            )
        return {
            "node_path": localize(opencl_node.path()),
            "context": "sop",
            "runover": runover,
            "binding_count": len(bindings),
            "bindings_match_kernel": bindings_match_kernel,
            "signature_matches_kernel": None,
            "sync_required": not bindings_match_kernel,
            "invalid_connection_count": 0,
            "missing_required_count": 0,
            "ok": bindings_match_kernel and not messages["errors"],
            "desired_bindings": desired_rows,
            "current_bindings": current_rows,
            "desired_inputs": [],
            "desired_outputs": [],
            "current_inputs": [],
            "current_outputs": [],
            "inputs": [],
            "hints": hints,
            **messages,
        }

    desired_inputs = _port_signature_entries(bindings, output=False)
    desired_outputs = _port_signature_entries(bindings, output=True)
    current_inputs = _summary_signature_entries(opencl_node, output=False)
    current_outputs = _summary_signature_entries(opencl_node, output=True)
    input_types = _input_data_types(opencl_node)
    connections = _current_input_connections(opencl_node)

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
    desired_output_rows = [{"name": entry["name"], "type": entry["type"]} for entry in desired_outputs]
    signature_matches_kernel = current_inputs == desired_input_rows and current_outputs == desired_output_rows
    messages = _node_messages(opencl_node)
    hints = _binding_row_hints(opencl_node)
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
        "current_outputs": current_outputs,
        "inputs": input_rows,
        "hints": hints,
        **messages,
    }


def _sync_bindings(opencl_node: Any, bindings: list[Any]) -> None:
    # Rebuild binding rows from an empty multiparm table so stale fields from
    # previous row kinds do not survive onto newly generated rows.
    opencl_node.setParms({"bindings": 0})
    if not bindings:
        return

    opencl_node.setParms({"bindings": len(bindings)})
    parm_values = _binding_row_values(bindings)
    if _is_sop_opencl(opencl_node):
        parm_values = {
            name: value
            for name, value in parm_values.items()
            if opencl_node.parm(name) is not None
        }
    opencl_node.setParms(parm_values)
    _link_binding_value_parms(opencl_node, bindings)


def _sync_signature(
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


def _apply_signature(
    session: Any,
    opencl_node: Any,
    bindings: list[Any],
    *,
    clear: bool,
    bindings_only: bool,
) -> dict[str, Any]:
    if _is_dop_opencl(opencl_node):
        if clear:
            opencl_node.setParms({"paramcount": 0})
        parm_bindings = [
            binding
            for binding in bindings
            if str(_binding_scalar(binding, "type")) in _DOP_SPARE_PARM_BINDING_TYPES
        ]
        spare_parms = _sync_spare_parms(session, opencl_node, parm_bindings)
        _sync_dop_bindings(opencl_node, bindings)
        return {
            "inputs": [],
            "outputs": [],
            "spare_parms": spare_parms,
        }

    if _is_sop_opencl(opencl_node):
        if clear:
            opencl_node.setParms({"bindings": 0})
        spare_parms = _sync_spare_parms(session, opencl_node, _parm_bindings(bindings))
        _sync_bindings(opencl_node, bindings)
        return {
            "inputs": [],
            "outputs": [],
            "spare_parms": spare_parms,
        }

    input_entries = _port_signature_entries(bindings, output=False)
    output_entries = _port_signature_entries(bindings, output=True)

    if not bindings_only and not clear:
        input_entries = _preserve_signature_order(
            _existing_signature_entries(opencl_node, output=False),
            input_entries,
        )
        output_entries = _preserve_signature_order(
            _existing_signature_entries(opencl_node, output=True),
            output_entries,
        )

    if clear:
        if bindings_only:
            opencl_node.setParms({"bindings": 0})
        else:
            opencl_node.setParms({"inputs": 0, "outputs": 0, "bindings": 0})

    parm_bindings = _parm_bindings(bindings)
    spare_parms = _sync_spare_parms(session, opencl_node, parm_bindings)

    _sync_bindings(opencl_node, parm_bindings)
    if not bindings_only:
        _sync_signature(opencl_node, input_entries, output_entries)

    return {
        "inputs": (
            _summary_signature_entries(opencl_node, output=False)
            if bindings_only
            else [{"name": entry["name"], "type": entry["type"], "optional": entry["optional"]} for entry in input_entries]
        ),
        "outputs": (
            _summary_signature_entries(opencl_node, output=True)
            if bindings_only
            else [{"name": entry["name"], "type": entry["type"]} for entry in output_entries]
        ),
        "spare_parms": spare_parms,
    }


def handle_sync(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        opencl_node = get_node(session, args.node_path)
        if opencl_node.parm("kernelcode") is None:
            raise ValueError(f"Node is not an OpenCL node: {args.node_path}")

        kernel_code = localize(opencl_node.parm("kernelcode").evalAsString())
        bindings = list(session.hou.text.oclExtractBindings(kernel_code))
        runover = str(localize(session.hou.text.oclExtractRunOver(kernel_code)))

        summary = _apply_signature(
            session,
            opencl_node,
            bindings,
            clear=args.clear,
            bindings_only=args.bindings_only,
        )
        if runover:
            runover_parm = opencl_node.parm("runover") or opencl_node.parm("options_runover")
            if runover_parm is not None:
                runover_parm.set(runover)

        validation = _validation_summary(opencl_node, bindings=bindings, runover=runover)
        disconnected_inputs: list[int] = []
        if getattr(args, "disconnect_invalid", False):
            for row in validation["inputs"]:
                if row["connected"] and row["compatible"] is False:
                    _disconnect_input(opencl_node, int(row["index"]))
                    disconnected_inputs.append(int(row["index"]))
            if disconnected_inputs:
                _safe_cook(opencl_node)
                validation = _validation_summary(opencl_node, bindings=bindings, runover=runover)

        data = {
            **_compact_validation(validation, bindings),
            "bindings_only": bool(args.bindings_only),
            "disconnect_invalid": bool(getattr(args, "disconnect_invalid", False)),
            "disconnected_inputs": disconnected_inputs,
            "spare_parms": summary["spare_parms"],
            "inputs": summary["inputs"],
            "outputs": summary["outputs"],
        }
        if getattr(args, "details", False):
            data["validation"] = validation
        return success_result(data)


def handle_validate(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        opencl_node = get_node(session, args.node_path)
        if opencl_node.parm("kernelcode") is None:
            raise ValueError(f"Node is not an OpenCL node: {args.node_path}")

        kernel_code = localize(opencl_node.parm("kernelcode").evalAsString())
        bindings = list(session.hou.text.oclExtractBindings(kernel_code))
        runover = str(localize(session.hou.text.oclExtractRunOver(kernel_code)))
        validation = _validation_summary(opencl_node, bindings=bindings, runover=runover)
        if getattr(args, "details", False):
            return success_result(validation)
        return success_result(_compact_validation(validation, bindings))
