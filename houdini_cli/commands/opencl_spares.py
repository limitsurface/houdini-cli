"""Generated spare parameter support for OpenCL commands."""

from __future__ import annotations

from typing import Any

from ..transport.rpyc import localize

SPARE_PARM_BINDING_TYPES = {"int", "float", "float2", "float3", "float4", "ramp"}


def _binding_scalar(binding: Any, key: str) -> Any:
    return localize(binding[key])


def _binding_vector(binding: Any, key: str, size: int) -> list[float]:
    value = binding[key]
    return [float(value[index]) for index in range(size)]


def spare_parm_name(binding: Any) -> str:
    return str(_binding_scalar(binding, "name"))


def _spare_parm_label(binding: Any) -> str:
    return spare_parm_name(binding).replace("_", " ").title()


def _spare_parm_template(session: Any, binding: Any) -> Any:
    binding_type = str(_binding_scalar(binding, "type"))
    name = spare_parm_name(binding)
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
    if binding_type == "ramp":
        ramp_type = (
            session.hou.rampParmType.Color
            if str(_binding_scalar(binding, "ramptype")) == "vector"
            else session.hou.rampParmType.Float
        )
        return session.hou.RampParmTemplate(
            name,
            label,
            ramp_type,
            default_value=2,
            default_basis=session.hou.rampBasis.Linear,
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
    return [spare_parm_name(binding) for binding in bindings]


def _sync_spare_parms(session: Any, opencl_node: Any, bindings: list[Any]) -> list[str]:
    desired_bindings = parm_bindings(bindings)
    _remove_generated_spare_parm_ui(opencl_node)

    if not desired_bindings:
        return []

    return _manual_sync_spare_parms(session, opencl_node, desired_bindings)


def spare_parm_component_names(opencl_node: Any, binding: Any) -> list[str]:
    name = spare_parm_name(binding)
    parm_tuple = getattr(opencl_node, "parmTuple", lambda _name: None)(name)
    if parm_tuple is None:
        parm_tuple = getattr(opencl_node, "parmTuple", lambda _name: None)(f"{name}_val")
    if parm_tuple is not None:
        try:
            return [str(localize(parm.name())) for parm in parm_tuple]
        except Exception:
            pass
    binding_type = str(_binding_scalar(binding, "type"))
    component_counts = {"float2": 2, "float3": 3, "float4": 4}
    count = component_counts.get(binding_type, 1)
    if count == 1:
        return [name]
    return [f"{name}{index}" for index in range(1, count + 1)]


def _capture_spare_parm_state(opencl_node: Any, bindings: list[Any]) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        for name in spare_parm_component_names(opencl_node, binding):
            parm = opencl_node.parm(name)
            if parm is None:
                continue
            state: dict[str, Any] = {}
            try:
                is_ramp = str(localize(parm.parmTemplate().type().name())) == "Ramp"
            except Exception:
                is_ramp = False
            if is_ramp:
                ramp = parm.eval()
                state["ramp"] = {
                    "basis": [str(localize(item.name())) for item in ramp.basis()],
                    "keys": [float(item) for item in ramp.keys()],
                    "values": list(localize(ramp.values())),
                }
                states[name] = state
                continue
            try:
                state["expression"] = parm.expression()
            except Exception:
                try:
                    state["value"] = localize(parm.eval())
                except Exception:
                    continue
            else:
                try:
                    state["language"] = parm.expressionLanguage()
                except Exception:
                    pass
            states[name] = state
    return states


def _restore_spare_parm_state(session: Any, opencl_node: Any, states: dict[str, dict[str, Any]]) -> None:
    for name, state in states.items():
        parm = opencl_node.parm(name)
        if parm is None:
            continue
        if "ramp" in state:
            ramp = state["ramp"]
            basis = tuple(getattr(session.hou.rampBasis, item) for item in ramp["basis"])
            parm.set(session.hou.Ramp(basis, tuple(ramp["keys"]), tuple(ramp["values"])))
            continue
        if "expression" in state:
            try:
                parm.setExpression(state["expression"], state.get("language"))
            except TypeError:
                parm.setExpression(state["expression"])
            continue
        if "value" in state:
            parm.set(state["value"])


def sync_spare_parms_preserving_values(
    session: Any,
    opencl_node: Any,
    bindings: list[Any],
    *,
    preserve: bool,
) -> list[str]:
    states = _capture_spare_parm_state(opencl_node, bindings) if preserve else {}
    spare_parms = _sync_spare_parms(session, opencl_node, bindings)
    if states:
        _restore_spare_parm_state(session, opencl_node, states)
    return spare_parms


def parm_bindings(bindings: list[Any]) -> list[Any]:
    return [
        binding
        for binding in bindings
        if str(_binding_scalar(binding, "type")) in SPARE_PARM_BINDING_TYPES
    ]


def set_binding_value_expression(opencl_node: Any, parm_name: str, expression: str) -> None:
    parm = opencl_node.parm(parm_name)
    if parm is not None:
        parm.setExpression(expression)


def link_binding_value_parms(opencl_node: Any, bindings: list[Any]) -> None:
    for index, binding in enumerate(bindings, start=1):
        binding_type = str(_binding_scalar(binding, "type"))
        spare_name = spare_parm_name(binding)
        expression = f'ch("./{spare_name}")'
        prefix = f"bindings{index}_"

        if binding_type == "int":
            set_binding_value_expression(opencl_node, f"{prefix}intval", expression)
        elif binding_type == "float":
            set_binding_value_expression(opencl_node, f"{prefix}fval", expression)
        elif binding_type == "float2":
            for component, source in enumerate(
                spare_parm_component_names(opencl_node, binding), start=1
            ):
                set_binding_value_expression(
                    opencl_node,
                    f"{prefix}v2val{component}",
                    f'ch("./{source}")',
                )
        elif binding_type == "float3":
            for component, source in enumerate(
                spare_parm_component_names(opencl_node, binding), start=1
            ):
                set_binding_value_expression(
                    opencl_node,
                    f"{prefix}v3val{component}",
                    f'ch("./{source}")',
                )
        elif binding_type == "float4":
            for component, source in enumerate(
                spare_parm_component_names(opencl_node, binding), start=1
            ):
                set_binding_value_expression(
                    opencl_node,
                    f"{prefix}v4val{component}",
                    f'ch("./{source}")',
                )
        elif binding_type == "ramp":
            suffix = "ramp_rgb" if str(_binding_scalar(binding, "ramptype")) == "vector" else "ramp"
            set_binding_value_expression(opencl_node, f"{prefix}{suffix}", f'ch("./{spare_name}")')
