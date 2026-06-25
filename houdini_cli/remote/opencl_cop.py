"""Remote payload builders for OpenCL COP validation."""

from __future__ import annotations

from .module import RemoteModule


SOURCE = r"""
import hou

SPARE_PARM_BINDING_TYPES = {"int", "float", "float2", "float3", "float4"}

def _houdini_cli_opencl_parm_expression(parm):
    if parm is None:
        return None
    try:
        return str(parm.expression())
    except Exception:
        return None

def _houdini_cli_opencl_binding_value_parm_names(index, binding_type):
    prefix = "bindings{}_".format(index)
    if binding_type == "int":
        return [(prefix + "intval", ("",))]
    if binding_type == "float":
        return [(prefix + "fval", ("",))]
    if binding_type == "float2":
        return [(prefix + "v2val{}".format(component), (str(component), "xy"[component - 1])) for component in range(1, 3)]
    if binding_type == "float3":
        return [(prefix + "v3val{}".format(component), (str(component), "xyz"[component - 1])) for component in range(1, 4)]
    if binding_type == "float4":
        return [(prefix + "v4val{}".format(component), (str(component), "xyzw"[component - 1])) for component in range(1, 5)]
    return []

def _houdini_cli_opencl_signature_entries(node, output):
    count_parm = node.parm("outputs" if output else "inputs")
    count = int(count_parm.eval()) if count_parm is not None else 0
    rows = []
    for index in range(1, count + 1):
        prefix = "output" if output else "input"
        name_parm = node.parm("{}{}_name".format(prefix, index))
        type_parm = node.parm("{}{}_type".format(prefix, index))
        if name_parm is None or type_parm is None:
            continue
        name = str(name_parm.evalAsString())
        if not name:
            continue
        row = {
            "name": name,
            "type": str(type_parm.evalAsString() or "floatn"),
            "optional": False,
        }
        if not output:
            optional_parm = node.parm("input{}_optional".format(index))
            row["optional"] = bool(optional_parm.eval()) if optional_parm is not None else False
        rows.append(row)
    return rows

def _houdini_cli_opencl_binding_hints(node):
    bindings_parm = node.parm("bindings")
    if bindings_parm is None:
        return []
    try:
        binding_count = int(bindings_parm.eval())
    except Exception:
        return []

    hints = []
    layer_rows = []
    static_rows = []
    for index in range(1, binding_count + 1):
        name_parm = node.parm("bindings{}_name".format(index))
        type_parm = node.parm("bindings{}_type".format(index))
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

        expected = 'ch("./{}")'.format(name)
        for parm_name, component_suffixes in _houdini_cli_opencl_binding_value_parm_names(index, binding_type):
            expr = _houdini_cli_opencl_parm_expression(node.parm(parm_name))
            expected_exprs = {
                expected if not component_suffix else 'ch("./{}{}")'.format(name, component_suffix)
                for component_suffix in component_suffixes
            }
            if expr not in expected_exprs:
                static_rows.append(name)
                break

    if layer_rows:
        hints.append(
            "OpenCL binding rows include layer bindings "
            + "({}); layer bindings should live in Signature inputs/outputs. ".format(", ".join(layer_rows))
            + "Try: houdini-cli opencl sync {}".format(node.path())
        )
    if static_rows:
        hints.append(
            "OpenCL parm binding rows are not linked to generated spare parms "
            + "({}); UI changes may not affect the kernel. ".format(", ".join(static_rows))
            + "Try: houdini-cli opencl sync {}".format(node.path())
        )
    return hints

def _houdini_cli_opencl_cop_validation_state(node_path):
    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)

    connections = {}
    for connection in node.inputConnections():
        source_node = connection.inputNode()
        output_index = int(connection.outputIndex())
        source_types = list(source_node.outputDataTypes()) if source_node is not None else []
        source_output_type = source_types[output_index] if 0 <= output_index < len(source_types) else None
        connections[int(connection.inputIndex())] = {
            "from_path": str(source_node.path()) if source_node is not None else None,
            "from_output_index": output_index,
            "from_output_name": str(connection.inputName()),
            "from_output_label": str(connection.inputLabel()),
            "source_output_type": source_output_type,
        }

    return {
        "current_inputs": _houdini_cli_opencl_signature_entries(node, False),
        "current_outputs": _houdini_cli_opencl_signature_entries(node, True),
        "input_types": [str(value) for value in node.inputDataTypes()],
        "connections": connections,
        "errors": [str(value) for value in node.errors()],
        "warnings": [str(value) for value in node.warnings()],
        "messages": [str(value) for value in node.messages()],
        "hints": _houdini_cli_opencl_binding_hints(node),
    }
"""

OPENCL_COP_REMOTE = RemoteModule(
    namespace="opencl_cop",
    source=SOURCE,
    entrypoints={"state": "_houdini_cli_opencl_cop_validation_state"},
)
