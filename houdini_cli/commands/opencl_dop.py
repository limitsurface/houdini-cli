"""Gas OpenCL DOP synchronization and validation."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize
from .opencl_bindings import binding_scalar, binding_vector, desired_binding_row_summary, node_messages
from .opencl_spares import set_binding_value_expression, spare_parm_name, sync_spare_parms_preserving_values


_DOP_SPARE_PARM_BINDING_TYPES = {"int", "float", "float3", "float4"}


def desired_or_current_dop_binding_row_summary(opencl_node: Any, bindings: list[Any]) -> list[dict[str, Any]]:
    if bindings:
        return desired_binding_row_summary(bindings)
    return dop_binding_row_summary(opencl_node)


def dop_binding_parm_values(index: int, binding: Any) -> dict[str, Any]:
    prefix = f"parameter{index}"
    binding_type = str(binding_scalar(binding, "type"))
    values: dict[str, Any] = {
        f"{prefix}Name": str(binding_scalar(binding, "name")),
        f"{prefix}Type": binding_type,
        f"{prefix}Precision": str(binding_scalar(binding, "precision")),
        f"{prefix}Input": bool(binding_scalar(binding, "readable")),
        f"{prefix}Output": bool(binding_scalar(binding, "writeable")),
        f"{prefix}Optional": bool(binding_scalar(binding, "optional")),
        f"{prefix}DefVal": bool(binding_scalar(binding, "defval")),
        f"{prefix}TimeScale": str(binding_scalar(binding, "timescale")),
    }

    if binding_type in {"scalarfield", "vectorfield", "matrixfield"}:
        values[f"{prefix}Field"] = str(binding_scalar(binding, "fieldname"))
        values[f"{prefix}Offsets"] = bool(binding_scalar(binding, "fieldoffsets"))
    elif binding_type == "attribute":
        values[f"{prefix}Geometry"] = str(binding_scalar(binding, "geometry"))
        values[f"{prefix}Attribute"] = str(binding_scalar(binding, "attribute"))
        values[f"{prefix}Class"] = str(binding_scalar(binding, "attribclass"))
        values[f"{prefix}AttributeType"] = str(binding_scalar(binding, "attribtype"))
        values[f"{prefix}AttributeSize"] = int(binding_scalar(binding, "attribsize"))
    elif binding_type == "volume":
        values[f"{prefix}Geometry"] = str(binding_scalar(binding, "geometry"))
        values[f"{prefix}Volume"] = str(binding_scalar(binding, "volume"))
        values[f"{prefix}Resolution"] = bool(binding_scalar(binding, "resolution"))
        values[f"{prefix}VoxelSize"] = bool(binding_scalar(binding, "voxelsize"))
        values[f"{prefix}XformToWorld"] = bool(binding_scalar(binding, "xformtoworld"))
        values[f"{prefix}XformToVoxel"] = bool(binding_scalar(binding, "xformtovoxel"))
    elif binding_type == "vdb":
        values[f"{prefix}Geometry"] = str(binding_scalar(binding, "geometry"))
        values[f"{prefix}Volume"] = str(binding_scalar(binding, "volume"))
        values[f"{prefix}VDBType"] = str(binding_scalar(binding, "vdbtype"))
    elif binding_type == "option":
        values[f"{prefix}DataName"] = str(binding_scalar(binding, "dataname"))
        values[f"{prefix}OptionName"] = str(binding_scalar(binding, "optionname"))
        values[f"{prefix}OptionType"] = str(binding_scalar(binding, "optiontype"))
        values[f"{prefix}OptionSize"] = int(binding_scalar(binding, "optionsize"))
    elif binding_type == "ramp":
        values[f"{prefix}RampSize"] = int(binding_scalar(binding, "rampsize"))
    elif binding_type == "int":
        values[f"{prefix}Int"] = int(binding_scalar(binding, "intval"))
    elif binding_type == "float":
        values[f"{prefix}Flt"] = float(binding_scalar(binding, "fval"))
    elif binding_type == "float3":
        values[f"{prefix}Flt3"] = binding_vector(binding, "v3val", 3)
    elif binding_type == "float4":
        values[f"{prefix}Flt4"] = binding_vector(binding, "v4val", 4)
    else:
        raise ValueError(f"Unsupported Gas OpenCL binding type: {binding_type}")

    return values


def dop_binding_row_summary(opencl_node: Any) -> list[dict[str, Any]]:
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


def link_dop_binding_value_parms(opencl_node: Any, bindings: list[Any]) -> None:
    suffixes = {
        "int": ["Int"],
        "float": ["Flt"],
        "float3": ["Flt31", "Flt32", "Flt33"],
        "float4": ["Flt41", "Flt42", "Flt43", "Flt44"],
    }
    for index, binding in enumerate(bindings, start=1):
        binding_type = str(binding_scalar(binding, "type"))
        spare_name = spare_parm_name(binding)
        for component, suffix in enumerate(suffixes.get(binding_type, []), start=1):
            target = f"parameter{index}{suffix}"
            source = spare_name if len(suffixes[binding_type]) == 1 else f"{spare_name}{component}"
            set_binding_value_expression(opencl_node, target, f'ch("./{source}")')


def sync_dop_bindings(opencl_node: Any, bindings: list[Any]) -> None:
    opencl_node.setParms({"paramcount": 0})
    if not bindings:
        return
    opencl_node.setParms({"paramcount": len(bindings)})
    parm_values: dict[str, Any] = {}
    for index, binding in enumerate(bindings, start=1):
        parm_values.update(dop_binding_parm_values(index, binding))
    parm_values = {
        name: value
        for name, value in parm_values.items()
        if opencl_node.parm(name) is not None
    }
    opencl_node.setParms(parm_values)
    link_dop_binding_value_parms(opencl_node, bindings)


def dop_validation_summary(opencl_node: Any, *, bindings: list[Any], runover: str) -> dict[str, Any]:
    current_rows = dop_binding_row_summary(opencl_node)
    desired_rows = desired_or_current_dop_binding_row_summary(opencl_node, bindings)
    bindings_match_kernel = current_rows == desired_rows
    messages = node_messages(opencl_node)
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
        "binding_count": len(desired_rows),
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


def apply_dop_signature(
    session: Any,
    opencl_node: Any,
    bindings: list[Any],
    *,
    clear: bool,
    preserve_spare_values: bool = False,
) -> dict[str, Any]:
    if clear:
        opencl_node.setParms({"paramcount": 0})
    spare_bindings = [
        binding
        for binding in bindings
        if str(binding_scalar(binding, "type")) in _DOP_SPARE_PARM_BINDING_TYPES
    ]
    spare_parms = sync_spare_parms_preserving_values(
        session,
        opencl_node,
        spare_bindings,
        preserve=preserve_spare_values,
    )
    sync_dop_bindings(opencl_node, bindings)
    return {
        "inputs": [],
        "outputs": [],
        "spare_parms": spare_parms,
    }
