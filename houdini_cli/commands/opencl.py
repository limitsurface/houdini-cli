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

    try:
        opencl_node.setParms({"inputs": 0, "outputs": 0, "bindings": 0})
        session.connection.modules.vexpressionmenu.createSpareParmsFromOCLBindings(
            opencl_node,
            "kernelcode",
        )
        return [_spare_parm_name(binding) for binding in desired_bindings]
    except Exception:
        return _manual_sync_spare_parms(session, opencl_node, desired_bindings)


def _apply_signature(session: Any, opencl_node: Any, bindings: list[Any], *, clear: bool) -> dict[str, Any]:
    input_bindings = [
        binding
        for binding in bindings
        if str(_binding_scalar(binding, "type")) in {"layer", "attribute", "volume", "vdb"}
        and bool(_binding_scalar(binding, "readable"))
    ]
    output_bindings = [
        binding
        for binding in bindings
        if str(_binding_scalar(binding, "type")) in {"layer", "attribute", "volume", "vdb"}
        and bool(_binding_scalar(binding, "writeable"))
    ]

    if clear:
        opencl_node.setParms({"inputs": 0, "outputs": 0, "bindings": 0})

    spare_parms = _sync_spare_parms(session, opencl_node, bindings)

    count_values: dict[str, Any] = {
        "inputs": len(input_bindings),
        "outputs": len(output_bindings),
        "bindings": len(bindings),
    }
    opencl_node.setParms(count_values)

    parm_values: dict[str, Any] = {}

    for index, binding in enumerate(input_bindings, start=1):
        binding_type = str(_binding_scalar(binding, "type"))
        parm_values[f"input{index}_name"] = str(_binding_scalar(binding, "name"))
        parm_values[f"input{index}_type"] = _signature_type(binding_type, binding, output=False)
        parm_values[f"input{index}_optional"] = bool(_binding_scalar(binding, "optional"))

    for index, binding in enumerate(output_bindings, start=1):
        binding_type = str(_binding_scalar(binding, "type"))
        parm_values[f"output{index}_name"] = str(_binding_scalar(binding, "name"))
        parm_values[f"output{index}_type"] = _signature_type(binding_type, binding, output=True)
        parm_values[f"output{index}_metadata"] = "first"
        parm_values[f"output{index}_precision"] = str(_binding_scalar(binding, "precision"))
        parm_values[f"output{index}_typeinfo"] = "node"
        parm_values[f"output{index}_metaname"] = ""

    for index, binding in enumerate(bindings, start=1):
        parm_values.update(_binding_parm_values(index, binding))
    opencl_node.setParms(parm_values)
    return {
        "inputs": [
            {
                "name": str(_binding_scalar(binding, "name")),
                "type": _signature_type(str(_binding_scalar(binding, "type")), binding, output=False),
                "optional": bool(_binding_scalar(binding, "optional")),
            }
            for binding in input_bindings
        ],
        "outputs": [
            {
                "name": str(_binding_scalar(binding, "name")),
                "type": _signature_type(str(_binding_scalar(binding, "type")), binding, output=True),
            }
            for binding in output_bindings
        ],
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

        summary = _apply_signature(session, opencl_node, bindings, clear=args.clear)
        if runover:
            opencl_node.parm("options_runover").set(runover)

        return success_result(
            {
                "node_path": localize(opencl_node.path()),
                "runover": runover,
                "binding_count": len(bindings),
                **summary,
            }
        )
