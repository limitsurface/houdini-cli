"""OpenCL SOP binding synchronization and validation."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize
from .opencl_bindings import (
    binding_row_summary,
    desired_or_current_binding_row_summary,
    node_messages,
    sync_bindings,
)
from .opencl_spares import parm_bindings, sync_spare_parms_preserving_values


def sop_validation_summary(opencl_node: Any, *, bindings: list[Any], runover: str) -> dict[str, Any]:
    current_rows = binding_row_summary(opencl_node)
    desired_rows = desired_or_current_binding_row_summary(opencl_node, bindings)
    bindings_match_kernel = current_rows == desired_rows
    messages = node_messages(opencl_node)
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


def apply_sop_signature(
    session: Any,
    opencl_node: Any,
    bindings: list[Any],
    *,
    clear: bool,
    preserve_spare_values: bool = True,
) -> dict[str, Any]:
    if clear:
        opencl_node.setParms({"bindings": 0})
    spare_parms = sync_spare_parms_preserving_values(
        session,
        opencl_node,
        parm_bindings(bindings),
        preserve=preserve_spare_values,
    )
    sync_bindings(opencl_node, bindings)
    return {
        "inputs": [],
        "outputs": [],
        "spare_parms": spare_parms,
    }
