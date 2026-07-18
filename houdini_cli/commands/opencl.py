"""OpenCL commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .node_common import get_node
from .opencl_bindings import (
    binding_scalar,
    compact_validation,
    is_cop_opencl,
    opencl_context,
    preflight_binding_types,
    safe_cook,
)
from .opencl_cop import (
    apply_cop_signature,
    cop_validation_state_in_houdini,
    cop_validation_summary,
    disconnect_input,
)
from .opencl_dop import apply_dop_signature, dop_validation_summary
from .opencl_sop import apply_sop_signature, sop_validation_summary


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
        "--preserve-spare-values",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preserve existing generated spare parameter values and expressions (enabled by default).",
    )
    sync_parser.add_argument(
        "--details",
        action="store_true",
        help="Include the full post-sync validation payload.",
    )
    sync_parser.set_defaults(handler=handle_sync)



def _apply_signature(
    session: Any,
    opencl_node: Any,
    bindings: list[Any],
    *,
    clear: bool,
    bindings_only: bool,
    preserve_spare_values: bool = True,
) -> dict[str, Any]:
    context = opencl_context(opencl_node)
    if context == "dop":
        return apply_dop_signature(
            session,
            opencl_node,
            bindings,
            clear=clear,
            preserve_spare_values=preserve_spare_values,
        )
    if context == "sop":
        return apply_sop_signature(
            session,
            opencl_node,
            bindings,
            clear=clear,
            preserve_spare_values=preserve_spare_values,
        )
    if context == "cop":
        return apply_cop_signature(
            session,
            opencl_node,
            bindings,
            clear=clear,
            bindings_only=bindings_only,
            preserve_spare_values=preserve_spare_values,
        )
    raise ValueError(f"Unsupported OpenCL context: {context}")


def _validation_summary(
    opencl_node: Any,
    *,
    bindings: list[Any],
    runover: str,
    current_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = opencl_context(opencl_node)
    if context == "dop":
        result = dop_validation_summary(opencl_node, bindings=bindings, runover=runover)
    elif context == "sop":
        result = sop_validation_summary(opencl_node, bindings=bindings, runover=runover)
    elif context == "cop":
        result = cop_validation_summary(
            opencl_node,
            bindings=bindings,
            runover=runover,
            current_state=current_state,
        )
    else:
        raise ValueError(f"Unsupported OpenCL context: {context}")
    bad_refs = [
        message
        for message in result.get("warnings", [])
        if "Bad parameter reference" in message
    ]
    if bad_refs:
        result["ok"] = False
        result["sync_required"] = True
        result.setdefault("hints", []).append("One or more OpenCL binding rows reference missing control parameters.")
    usecode = opencl_node.parm("usecode")
    if (
        usecode is not None
        and not bool(usecode.eval())
        and opencl_node.parm("kernelcode").evalAsString()
    ):
        result["ok"] = False
        result["sync_required"] = True
        result.setdefault("hints", []).append(
            "Kernel Code is populated but Use Code Snippet is disabled; opencl sync will enable it."
        )
    atbinding = opencl_node.parm("atbinding")
    kernel_code = opencl_node.parm("kernelcode").evalAsString()
    if (
        atbinding is not None
        and ("#bind" in kernel_code or "@KERNEL" in kernel_code)
        and not bool(atbinding.eval())
    ):
        result["ok"] = False
        result["sync_required"] = True
        result.setdefault("hints", []).append(
            "Kernel Code uses @-binding directives but Enable @-Binding is disabled; opencl sync will enable it."
        )
    return result


def handle_sync(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        opencl_node = get_node(session, args.node_path)
        if opencl_node.parm("kernelcode") is None:
            raise ValueError(f"Node is not an OpenCL node: {args.node_path}")

        kernel_code = localize(opencl_node.parm("kernelcode").evalAsString())
        bindings = list(session.hou.text.oclExtractBindings(kernel_code))
        runover = str(localize(session.hou.text.oclExtractRunOver(kernel_code)))

        if not kernel_code.strip():
            raise ValueError("Kernel Code is empty; OpenCL sync does not rebuild external-kernel interfaces.")
        preflight_binding_types(opencl_node, bindings)
        usecode = opencl_node.parm("usecode")
        if usecode is not None and not bool(usecode.eval()):
            usecode.set(True)
        atbinding = opencl_node.parm("atbinding")
        if (
            atbinding is not None
            and ("#bind" in kernel_code or "@KERNEL" in kernel_code)
            and not bool(atbinding.eval())
        ):
            atbinding.set(True)

        summary = _apply_signature(
            session,
            opencl_node,
            bindings,
            clear=args.clear,
            bindings_only=args.bindings_only,
            preserve_spare_values=getattr(args, "preserve_spare_values", True),
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
                    disconnect_input(opencl_node, int(row["index"]))
                    disconnected_inputs.append(int(row["index"]))
            if disconnected_inputs:
                safe_cook(opencl_node)
                validation = _validation_summary(opencl_node, bindings=bindings, runover=runover)

        data = {
            **compact_validation(validation, bindings),
            "bindings_only": bool(args.bindings_only),
            "disconnect_invalid": bool(getattr(args, "disconnect_invalid", False)),
            "preserve_spare_values": bool(getattr(args, "preserve_spare_values", True)),
            "disconnected_inputs": disconnected_inputs,
            "spare_parms": summary["spare_parms"],
            "inputs": summary["inputs"],
            "outputs": summary["outputs"],
        }
        if "restored_connections" in summary:
            data["restored_connections"] = summary["restored_connections"]
            data["dropped_connections"] = summary["dropped_connections"]
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
        safe_cook(opencl_node)
        current_state = (
            cop_validation_state_in_houdini(session, args.node_path)
            if is_cop_opencl(opencl_node)
            else None
        )
        validation = _validation_summary(
            opencl_node,
            bindings=bindings,
            runover=runover,
            current_state=current_state,
        )
        if getattr(args, "details", False):
            return success_result(validation)
        return success_result(compact_validation(validation, bindings))
