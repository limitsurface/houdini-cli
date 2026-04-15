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


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    opencl_parser = subparsers.add_parser("opencl", help="Inspect and synchronize OpenCL nodes.")
    opencl_subparsers = opencl_parser.add_subparsers(dest="opencl_command", required=True)

    validate_parser = opencl_subparsers.add_parser(
        "validate",
        help="Validate an OpenCL node's current signature and wired input types against its kernel.",
    )
    validate_parser.add_argument("node_path", help="OpenCL node path.")
    validate_parser.set_defaults(handler=handle_validate)

    sync_parser = opencl_subparsers.add_parser(
        "sync",
        help="Rebuild OpenCL signature and bindings from #bind directives.",
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
        help="Update binding rows and generated spare parms without changing visible inputs/outputs.",
    )
    sync_parser.add_argument(
        "--disconnect-invalid",
        action="store_true",
        help="After syncing, disconnect any wired inputs whose source output type no longer matches the regenerated input type.",
    )
    sync_parser.set_defaults(handler=handle_sync)


def _binding_scalar(binding: Any, key: str) -> Any:
    return localize(binding[key])


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
        values[f"{prefix}v2val"] = list(localize(binding["v2val"]))
    elif binding_type == "float3":
        values[f"{prefix}v3val"] = list(localize(binding["v3val"]))
    elif binding_type == "float4":
        values[f"{prefix}v4val"] = list(localize(binding["v4val"]))

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
            default_value=tuple(float(value) for value in localize(binding["v2val"])),
        )
    if binding_type == "float3":
        return session.hou.FloatParmTemplate(
            name,
            label,
            3,
            default_value=tuple(float(value) for value in localize(binding["v3val"])),
        )
    if binding_type == "float4":
        return session.hou.FloatParmTemplate(
            name,
            label,
            4,
            default_value=tuple(float(value) for value in localize(binding["v4val"])),
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


def _binding_row_values(bindings: list[Any]) -> dict[str, Any]:
    parm_values: dict[str, Any] = {}
    for index, binding in enumerate(bindings, start=1):
        parm_values.update(_binding_parm_values(index, binding))
    return parm_values


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
        name = row.get(name_key)
        if not name:
            continue
        entry: dict[str, Any] = {
            "name": str(name),
            "type": str(row.get(type_key) or "floatn"),
            "optional": bool(row.get(optional_key, False)) if not output else False,
        }
        result.append(entry)
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

    return {
        "node_path": localize(opencl_node.path()),
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
        **messages,
    }


def _sync_bindings(opencl_node: Any, bindings: list[Any]) -> None:
    # Rebuild binding rows from an empty multiparm table so stale fields from
    # previous row kinds do not survive onto newly generated rows.
    opencl_node.setParms({"bindings": 0})
    if not bindings:
        return

    opencl_node.setParms({"bindings": len(bindings)})
    opencl_node.setParms(_binding_row_values(bindings))


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

    spare_parms = _sync_spare_parms(session, opencl_node, bindings)

    _sync_bindings(opencl_node, bindings)
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
            opencl_node.parm("options_runover").set(runover)

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

        return success_result(
            {
                "node_path": localize(opencl_node.path()),
                "runover": runover,
                "binding_count": len(bindings),
                "bindings_only": bool(args.bindings_only),
                "disconnect_invalid": bool(getattr(args, "disconnect_invalid", False)),
                "disconnected_inputs": disconnected_inputs,
                **summary,
                "validation": validation,
            }
        )


def handle_validate(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        opencl_node = get_node(session, args.node_path)
        if opencl_node.parm("kernelcode") is None:
            raise ValueError(f"Node is not an OpenCL node: {args.node_path}")

        kernel_code = localize(opencl_node.parm("kernelcode").evalAsString())
        bindings = list(session.hou.text.oclExtractBindings(kernel_code))
        runover = str(localize(session.hou.text.oclExtractRunOver(kernel_code)))
        return success_result(_validation_summary(opencl_node, bindings=bindings, runover=runover))
