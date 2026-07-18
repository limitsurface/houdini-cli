"""Shared OpenCL binding helpers."""

from __future__ import annotations

import re
from typing import Any

from ..transport.rpyc import localize
from .opencl_spares import SPARE_PARM_BINDING_TYPES, link_binding_value_parms, spare_parm_name


def binding_scalar(binding: Any, key: str) -> Any:
    return localize(binding[key])


def binding_value(binding: Any, key: str, default: Any) -> Any:
    try:
        return localize(binding[key])
    except (KeyError, TypeError):
        return default


_BIND_DIRECTIVE_RE = re.compile(r"(?m)^[ \t]*#bind\b([^\r\n]*)")
_BVH_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:pointbvhmask\s*=\s*[^\s/]+|nopointbvh|pointbvh|nobvh|bvh)"
)


def enrich_bvh_bindings(kernel_code: str, bindings: list[Any]) -> list[Any]:
    """Restore H22 BVH modifiers omitted by hou.text.oclExtractBindings()."""
    directives = _BIND_DIRECTIVE_RE.findall(kernel_code)
    enriched: list[Any] = []
    for index, binding in enumerate(bindings):
        row = dict(binding)
        row.setdefault("bvh", False)
        row.setdefault("pointbvh", False)
        row.setdefault("pointbvhmask", "")
        if index < len(directives) and str(row.get("type", "")) == "attribute":
            source = directives[index].split("//", 1)[0]
            bvh = False
            pointbvh = False
            pointbvhmask = ""
            for match in _BVH_TOKEN_RE.finditer(source):
                token = match.group(0)
                compact = re.sub(r"\s+", "", token)
                if compact == "bvh":
                    bvh = True
                elif compact == "nobvh":
                    bvh = False
                elif compact == "pointbvh":
                    pointbvh = True
                elif compact == "nopointbvh":
                    pointbvh = False
                elif compact.startswith("pointbvhmask="):
                    pointbvhmask = compact.split("=", 1)[1]
            row["bvh"] = bvh
            row["pointbvh"] = pointbvh
            row["pointbvhmask"] = pointbvhmask
        enriched.append(row)
    return enriched


def bvh_summary(binding: Any) -> dict[str, Any]:
    return {
        "bvh": bool(binding_value(binding, "bvh", False)),
        "pointbvh": bool(binding_value(binding, "pointbvh", False)),
        "pointbvhmask": str(binding_value(binding, "pointbvhmask", "")),
    }


def accelerated_binding_summaries(bindings: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for binding in bindings:
        accel = bvh_summary(binding)
        if not any(accel.values()):
            continue
        mode = "surface_bvh" if accel["bvh"] else "point_bvh" if accel["pointbvh"] else "none"
        row = {"name": str(binding_scalar(binding, "name")), "mode": mode}
        if accel["pointbvhmask"]:
            row["point_mask"] = accel["pointbvhmask"]
        rows.append(row)
    return rows


def preflight_bvh_bindings(session: Any, opencl_node: Any, bindings: list[Any]) -> None:
    accelerated = [binding for binding in bindings if any(bvh_summary(binding).values())]
    if not accelerated:
        return

    try:
        major = int(localize(session.hou.applicationVersion())[0])
    except Exception:
        major = 22
    if major < 22:
        raise ValueError("OpenCL BVH attribute bindings require Houdini 22 or newer.")

    for binding in accelerated:
        name = str(binding_scalar(binding, "name"))
        accel = bvh_summary(binding)
        if accel["bvh"] and accel["pointbvh"]:
            raise ValueError(f"OpenCL binding {name!r} cannot combine bvh and pointbvh.")
        if str(binding_scalar(binding, "type")) != "attribute":
            raise ValueError(f"OpenCL BVH binding {name!r} must be an attribute binding.")
        if not bool(binding_scalar(binding, "readable")):
            raise ValueError(f"OpenCL BVH binding {name!r} must be readable.")
        attribclass = str(binding_scalar(binding, "attribclass"))
        attribtype = str(binding_scalar(binding, "attribtype"))
        attribsize = int(binding_scalar(binding, "attribsize"))
        if attribtype != "float" or attribsize != 3:
            raise ValueError(f"OpenCL BVH binding {name!r} must be a float3 attribute.")
        if accel["bvh"] and attribclass not in {"point", "vertex"}:
            raise ValueError(f"Surface BVH binding {name!r} must use a point or vertex attribute.")
        if accel["pointbvh"] and attribclass != "point":
            raise ValueError(f"Point BVH binding {name!r} must use a point attribute.")
        if accel["pointbvhmask"] and not accel["pointbvh"]:
            raise ValueError(f"OpenCL binding {name!r} uses pointbvhmask without pointbvh.")


def binding_vector(binding: Any, key: str, size: int) -> list[float]:
    value = binding[key]
    return [float(value[index]) for index in range(size)]


def binding_parm_values(index: int, binding: Any) -> dict[str, Any]:
    prefix = f"bindings{index}_"
    binding_type = str(binding_scalar(binding, "type"))
    values: dict[str, Any] = {
        f"{prefix}name": str(binding_scalar(binding, "name")),
        f"{prefix}type": binding_type,
        f"{prefix}portname": str(binding_scalar(binding, "portname")),
        f"{prefix}precision": str(binding_scalar(binding, "precision")),
        f"{prefix}optional": bool(binding_scalar(binding, "optional")),
        f"{prefix}defval": bool(binding_scalar(binding, "defval")),
        f"{prefix}readable": bool(binding_scalar(binding, "readable")),
        f"{prefix}writeable": bool(binding_scalar(binding, "writeable")),
        f"{prefix}timescale": str(binding_scalar(binding, "timescale")),
    }

    if binding_type == "layer":
        values[f"{prefix}layertype"] = str(binding_scalar(binding, "layertype"))
        values[f"{prefix}layerborder"] = str(binding_scalar(binding, "layerborder"))
    elif binding_type == "attribute":
        values[f"{prefix}input"] = int(binding_scalar(binding, "input"))
        values[f"{prefix}attribute"] = str(binding_scalar(binding, "attribute"))
        values[f"{prefix}attribclass"] = str(binding_scalar(binding, "attribclass"))
        values[f"{prefix}attribtype"] = str(binding_scalar(binding, "attribtype"))
        values[f"{prefix}attribsize"] = int(binding_scalar(binding, "attribsize"))
        accel = bvh_summary(binding)
        values[f"{prefix}attribbvh"] = accel["bvh"]
        values[f"{prefix}attribpointbvh"] = accel["pointbvh"]
        values[f"{prefix}attribpointbvhmask"] = accel["pointbvhmask"]
    elif binding_type == "volume":
        values[f"{prefix}input"] = int(binding_scalar(binding, "input"))
        values[f"{prefix}volume"] = str(binding_scalar(binding, "volume"))
        values[f"{prefix}resolution"] = bool(binding_scalar(binding, "resolution"))
        values[f"{prefix}voxelsize"] = bool(binding_scalar(binding, "voxelsize"))
        values[f"{prefix}xformtoworld"] = bool(binding_scalar(binding, "xformtoworld"))
        values[f"{prefix}xformtovoxel"] = bool(binding_scalar(binding, "xformtovoxel"))
    elif binding_type == "vdb":
        values[f"{prefix}input"] = int(binding_scalar(binding, "input"))
        values[f"{prefix}volume"] = str(binding_scalar(binding, "volume"))
        values[f"{prefix}vdbtype"] = str(binding_scalar(binding, "vdbtype"))
    elif binding_type == "int":
        values[f"{prefix}intval"] = int(binding_scalar(binding, "intval"))
    elif binding_type == "float":
        values[f"{prefix}fval"] = float(binding_scalar(binding, "fval"))
    elif binding_type == "float2":
        values[f"{prefix}v2val"] = binding_vector(binding, "v2val", 2)
    elif binding_type == "float3":
        values[f"{prefix}v3val"] = binding_vector(binding, "v3val", 3)
    elif binding_type == "float4":
        values[f"{prefix}v4val"] = binding_vector(binding, "v4val", 4)
    elif binding_type == "ramp":
        values[f"{prefix}rampsize"] = int(binding_scalar(binding, "rampsize"))
        values[f"{prefix}ramptype"] = str(binding_scalar(binding, "ramptype"))

    return values


def binding_row_values(bindings: list[Any]) -> dict[str, Any]:
    parm_values: dict[str, Any] = {}
    for index, binding in enumerate(bindings, start=1):
        parm_values.update(binding_parm_values(index, binding))
    return parm_values


def node_category(opencl_node: Any) -> str:
    try:
        return str(localize(opencl_node.type().category().name()))
    except Exception:
        return ""


def is_sop_opencl(opencl_node: Any) -> bool:
    return node_category(opencl_node).lower() == "sop"


def is_dop_opencl(opencl_node: Any) -> bool:
    return node_category(opencl_node).lower() == "dop"


def opencl_context(opencl_node: Any) -> str:
    if is_sop_opencl(opencl_node):
        return "sop"
    if is_dop_opencl(opencl_node):
        return "dop"
    return "cop"


def is_cop_opencl(opencl_node: Any) -> bool:
    return opencl_context(opencl_node) == "cop"


def data_scalar(value: Any) -> Any:
    while isinstance(value, dict) and "value" in value:
        value = value["value"]
    return value


def compact_binding_rows(bindings: list[Any]) -> list[list[Any]]:
    rows = []
    for binding in bindings:
        binding_type = str(binding_scalar(binding, "type"))
        readable = bool(binding_scalar(binding, "readable"))
        writeable = bool(binding_scalar(binding, "writeable"))
        if binding_type in SPARE_PARM_BINDING_TYPES:
            direction = "parm"
        elif readable and writeable:
            direction = "inout"
        elif writeable:
            direction = "output"
        else:
            direction = "input"
        rows.append([spare_parm_name(binding), binding_type, direction])
    return rows


def compact_binding_row_summaries(rows: list[dict[str, Any]]) -> list[list[Any]]:
    result = []
    for row in rows:
        binding_type = str(row["type"])
        direction = "parm" if binding_type in SPARE_PARM_BINDING_TYPES else "input"
        result.append([str(row["name"]), binding_type, direction])
    return result


def compact_validation(validation: dict[str, Any], bindings: list[Any]) -> dict[str, Any]:
    binding_rows = (
        compact_binding_rows(bindings)
        if bindings
        else compact_binding_row_summaries(validation.get("current_bindings", []))
    )
    result = {
        "node_path": validation["node_path"],
        "context": validation.get("context", "cop"),
        "runover": validation.get("runover", ""),
        "binding_count": validation["binding_count"],
        "binding_cols": ["name", "type", "direction"],
        "bindings": binding_rows,
        "clean": bool(validation["ok"]),
        "sync_required": bool(validation.get("sync_required", False)),
        "invalid_connection_count": validation.get("invalid_connection_count", 0),
        "missing_required_count": validation.get("missing_required_count", 0),
    }
    for key in ("errors", "warnings", "messages", "hints"):
        if validation.get(key):
            result[key] = validation[key]
    if validation.get("accelerated_bindings"):
        result["accelerated_bindings"] = validation["accelerated_bindings"]
    return result

def node_messages(opencl_node: Any) -> dict[str, list[str]]:
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

def binding_row_summary(opencl_node: Any) -> list[dict[str, Any]]:
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
                    "bvh": bool(opencl_node.parm(f"bindings{index}_attribbvh").eval())
                    if opencl_node.parm(f"bindings{index}_attribbvh") is not None
                    else False,
                    "pointbvh": bool(opencl_node.parm(f"bindings{index}_attribpointbvh").eval())
                    if opencl_node.parm(f"bindings{index}_attribpointbvh") is not None
                    else False,
                    "pointbvhmask": str(opencl_node.parm(f"bindings{index}_attribpointbvhmask").evalAsString())
                    if opencl_node.parm(f"bindings{index}_attribpointbvhmask") is not None
                    else "",
                }
            )
        except Exception:
            continue
    return rows


def desired_binding_row_summary(bindings: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": str(binding_scalar(binding, "name")),
            "type": str(binding_scalar(binding, "type")),
            **bvh_summary(binding),
        }
        for binding in bindings
    ]


def desired_or_current_binding_row_summary(opencl_node: Any, bindings: list[Any]) -> list[dict[str, Any]]:
    if bindings:
        return desired_binding_row_summary(bindings)
    return binding_row_summary(opencl_node)

def sync_bindings(opencl_node: Any, bindings: list[Any]) -> None:
    # Rebuild binding rows from an empty multiparm table so stale fields from
    # previous row kinds do not survive onto newly generated rows.
    opencl_node.setParms({"bindings": 0})
    if not bindings:
        return

    opencl_node.setParms({"bindings": len(bindings)})
    parm_values = binding_row_values(bindings)
    if is_sop_opencl(opencl_node):
        parm_values = {
            name: value
            for name, value in parm_values.items()
            if opencl_node.parm(name) is not None
        }
    opencl_node.setParms(parm_values)
    link_binding_value_parms(opencl_node, bindings)


def safe_cook(node: Any) -> None:
    cook = getattr(node, "cook", None)
    if not callable(cook):
        return
    try:
        cook(force=True)
    except TypeError:
        cook()
    except Exception:
        return


def _nested_parm_templates(template: Any) -> list[Any]:
    result = []
    for child in getattr(template, "parmTemplates", lambda: ())():
        result.append(child)
        result.extend(_nested_parm_templates(child))
    return result


def supported_binding_types(opencl_node: Any) -> set[str] | None:
    context = opencl_context(opencl_node)
    count_name = "paramcount" if context == "dop" else "bindings"
    type_suffix = "Type" if context == "dop" else "_type"
    count_parm = opencl_node.parm(count_name)
    if count_parm is None:
        return None
    try:
        templates = _nested_parm_templates(count_parm.parmTemplate())
        type_template = next(
            template
            for template in templates
            if str(template.name()).endswith(type_suffix)
        )
        return {str(item) for item in type_template.menuItems()}
    except Exception:
        return None


def preflight_binding_types(opencl_node: Any, bindings: list[Any]) -> None:
    supported = supported_binding_types(opencl_node)
    if not supported:
        return
    unsupported = [
        (str(binding_scalar(binding, "name")), str(binding_scalar(binding, "type")))
        for binding in bindings
        if str(binding_scalar(binding, "type")) not in supported
    ]
    if unsupported:
        details = ", ".join(f"{name} ({kind})" for name, kind in unsupported)
        raise ValueError(
            f"Unsupported OpenCL {opencl_context(opencl_node).upper()} bindings for this Houdini build: {details}. "
            f"Supported types: {', '.join(sorted(supported))}"
        )
