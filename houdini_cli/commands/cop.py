"""Copernicus commands."""

from __future__ import annotations

import argparse
import math
import os
import re
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from ..util.jsonio import load_json_input
from .node_common import get_node


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    cop_parser = subparsers.add_parser("cop", help="Inspect cooked Copernicus data.")
    cop_subparsers = cop_parser.add_subparsers(dest="cop_command", required=True)

    info_parser = cop_subparsers.add_parser("info", help="Read cooked metadata for a COP output.")
    info_parser.add_argument("node_path", help="COP node path.")
    info_parser.add_argument("--output", help="Output index or output name when querying a multi-output COP directly.")
    info_parser.set_defaults(handler=handle_info)

    sample_parser = cop_subparsers.add_parser("sample", help="Sample cooked pixel values from a COP output.")
    sample_parser.add_argument("node_path", help="COP node path.")
    sample_parser.add_argument("--output", default="0", help="Output index or output name (default: 0).")
    sample_group = sample_parser.add_mutually_exclusive_group(required=True)
    sample_group.add_argument("--points", help="JSON array of points or '-' to read from stdin.")
    sample_group.add_argument("--x", type=int, help="Pixel X coordinate.")
    sample_parser.add_argument("--y", type=int, help="Pixel Y coordinate.")
    sample_parser.set_defaults(handler=handle_sample)

    export_parser = cop_subparsers.add_parser("export-image", help="Export a COP output as a raw or view-transformed image.")
    export_parser.add_argument("node_path", help="COP node path.")
    export_parser.add_argument("--mode", required=True, choices=("raw", "view"), help="Export raw data EXR or view-baked image.")
    export_parser.add_argument("--output", help="Destination image path. Defaults to $JOB/tex/cli_images or $HIP/tex/cli_images.")
    export_parser.add_argument("--aov", "--layer", dest="aov", help="COP output index or output name (default: inferred/0).")
    export_parser.add_argument("--display", help="OCIO display for --mode view.")
    export_parser.add_argument("--view", help="OCIO view for --mode view.")
    export_parser.set_defaults(handler=handle_export_image)

    import_parser = cop_subparsers.add_parser("import-image", help="Create a File COP for an image on disk.")
    import_parser.add_argument("image_path", help="Image file path, including Houdini variables such as $JOB when useful.")
    import_parser.add_argument("--parent", required=True, help="Destination Copernicus network path.")
    import_parser.add_argument("--name", help="Created File COP node name.")
    import_parser.add_argument("--colorspace", choices=("ocio", "raw"), default="ocio", help="File COP incoming colorspace (default: ocio).")
    import_parser.add_argument("--set-display", action="store_true", help="Set the created File COP display/render flags.")
    import_parser.set_defaults(handler=handle_import_image)


def _resolve_output_index(node: Any, output_ref: str) -> int:
    try:
        return int(output_ref)
    except ValueError:
        pass

    output_names = list(localize(node.outputNames()))
    output_labels = list(localize(node.outputLabels()))
    if output_ref in output_names:
        return output_names.index(output_ref)
    if output_ref in output_labels:
        return output_labels.index(output_ref)
    if output_ref not in output_names:
        raise ValueError(f"Output not found on node {localize(node.path())}: {output_ref}")
    return output_names.index(output_ref)


def _output_identity(node: Any, output_index: int) -> dict[str, Any]:
    output_names = list(localize(node.outputNames()))
    output_labels = list(localize(node.outputLabels()))
    output_types = [str(localize(value)) for value in node.outputDataTypes()]
    return {
        "output_index": output_index,
        "output_name": output_names[output_index],
        "output_label": output_labels[output_index],
        "output_data_type": output_types[output_index],
    }


def _connection_output_identity(connection: Any) -> dict[str, Any]:
    source_node = connection.inputNode()
    output_index = int(localize(connection.outputIndex()))
    if source_node is not None:
        output_names = list(localize(source_node.outputNames()))
        output_labels = list(localize(source_node.outputLabels()))
        output_types = [str(localize(value)) for value in source_node.outputDataTypes()]
        if 0 <= output_index < len(output_names):
            return {
                "output_index": output_index,
                "output_name": output_names[output_index],
                "output_label": output_labels[output_index],
                "output_data_type": output_types[output_index],
            }
    return {
        "output_index": output_index,
        "output_name": str(localize(connection.outputName())),
        "output_label": str(localize(connection.outputLabel())),
    }


def _first_input_connection(node: Any) -> Any | None:
    try:
        connections = list(node.inputConnections())
    except Exception:
        return None
    return connections[0] if connections else None


def _is_output_proxy_node(node: Any) -> bool:
    try:
        type_name = str(localize(node.type().name()))
    except Exception:
        return True
    return type_name == "null"


def _find_output_proxy_node(node: Any, output_index: int) -> Any | None:
    for child in list(node.outputs()):
        if not _is_output_proxy_node(child):
            continue
        try:
            input_connections = list(child.inputConnections())
        except Exception:
            continue
        for connection in input_connections:
            source = connection.inputNode()
            if source is None:
                continue
            if localize(source.path()) != localize(node.path()):
                continue
            if int(localize(connection.outputIndex())) == output_index:
                return child
    return None


def _resolve_layer_target(node: Any, output_ref: str | None) -> tuple[Any, int, dict[str, Any]]:
    output_names = list(localize(node.outputNames()))
    if output_ref is not None or len(output_names) > 1:
        resolved_ref = output_ref if output_ref is not None else "0"
        output_index = _resolve_output_index(node, resolved_ref)
        identity = {
            "source_node_path": localize(node.path()),
            **_output_identity(node, output_index),
        }
        if len(output_names) == 1 and output_index == 0:
            return node, output_index, identity
        proxy = _find_output_proxy_node(node, output_index)
        if proxy is not None:
            return proxy, 0, identity
        return node, output_index, identity

    upstream = _first_input_connection(node)
    if upstream is not None and upstream.inputNode() is not None and _is_output_proxy_node(node):
        source_node = upstream.inputNode()
        identity = {
            "source_node_path": localize(source_node.path()),
            **_connection_output_identity(upstream),
        }
        return node, 0, identity

    identity = {
        "source_node_path": localize(node.path()),
        **_output_identity(node, 0),
    }
    return node, 0, identity


def _rect_payload(rect: Any) -> dict[str, int]:
    minimum = rect.min()
    maximum = rect.max()
    size = rect.size()
    return {
        "min_x": int(minimum[0]),
        "min_y": int(minimum[1]),
        "max_x": int(maximum[0]),
        "max_y": int(maximum[1]),
        "width": int(size[0]),
        "height": int(size[1]),
    }


def _normalize_points(args: argparse.Namespace) -> list[dict[str, int]]:
    if args.points is not None:
        payload = load_json_input(args.points)
        if not isinstance(payload, list):
            raise ValueError("--points must be a JSON array")
        points: list[dict[str, int]] = []
        for item in payload:
            if not isinstance(item, dict) or "x" not in item or "y" not in item:
                raise ValueError("Each point must be an object with x and y fields")
            points.append({"x": int(item["x"]), "y": int(item["y"])})
        return points

    if args.x is None or args.y is None:
        raise ValueError("Both --x and --y are required when --points is not used")
    return [{"x": args.x, "y": args.y}]


def _sample_point(layer: Any, x: int, y: int) -> dict[str, Any]:
    buffer_position = localize(layer.pixelToBuffer((x, y)))
    # pixelToBuffer returns coordinates centered on the pixel footprint,
    # so convert back to the nearest discrete buffer element.
    buffer_x = math.floor(buffer_position[0] + 0.5)
    buffer_y = math.floor(buffer_position[1] + 0.5)
    buffer_width, buffer_height = localize(layer.bufferResolution())
    if not (0 <= buffer_x < buffer_width and 0 <= buffer_y < buffer_height):
        raise ValueError(f"Point is outside the layer buffer: ({x}, {y})")
    return {
        "x": x,
        "y": y,
        "buffer_x": int(buffer_x),
        "buffer_y": int(buffer_y),
        "value": localize(layer.bufferIndex(int(buffer_x), int(buffer_y))),
    }


def _layer_payload(layer: Any) -> dict[str, Any]:
    return {
        "resolution": {
            "buffer": list(localize(layer.bufferResolution())),
            "data_window": _rect_payload(layer.dataWindow()),
            "display_window": _rect_payload(layer.displayWindow()),
            "pixel_scale": list(localize(layer.pixelScale())),
            "pixel_aspect_ratio": float(localize(layer.pixelAspectRatio())),
        },
        "channel_count": int(localize(layer.channelCount())),
        "storage": {
            "type": str(layer.storageType()),
            "border": str(layer.border()),
            "type_info": str(layer.typeInfo()),
            "is_constant": bool(localize(layer.isConstant())),
            "on_cpu": bool(localize(layer.onCPU())),
            "on_gpu": bool(localize(layer.onGPU())),
            "stores_integers": bool(localize(layer.storesIntegers())),
        },
    }


def _set_parm(node: Any, name: str, value: Any, *, required: bool = True) -> bool:
    parm = node.parm(name)
    if parm is None:
        if required:
            raise ValueError(f"Parameter not found on {localize(node.path())}: {name}")
        return False
    parm.set(value)
    return True


def _set_menu_parm(node: Any, name: str, token: str, *, required: bool = True) -> bool:
    parm = node.parm(name)
    if parm is None:
        if required:
            raise ValueError(f"Parameter not found on {localize(node.path())}: {name}")
        return False

    items = list(localize(parm.parmTemplate().menuItems()))
    if token not in items:
        raise ValueError(f"Menu item not found on {localize(node.path())}/{name}: {token}")
    index = items.index(token)
    try:
        current = localize(parm.eval())
    except Exception:
        current = None
    parm.set(index if isinstance(current, int) else token)
    return True


def _press_button(node: Any, name: str) -> bool:
    parm = node.parm(name)
    if parm is None:
        return False
    parm.pressButton()
    return True


def _sanitized_name(value: str, *, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def _unique_child_name(parent: Any, base_name: str) -> str:
    if parent.node(base_name) is None:
        return base_name
    index = 1
    while parent.node(f"{base_name}_{index}") is not None:
        index += 1
    return f"{base_name}_{index}"


def _expanded_env_path(session: Any, variable: str) -> str | None:
    raw = localize(session.hou.getenv(variable) or "")
    expanded = localize(session.hou.expandString(f"${variable}"))
    if raw:
        return expanded
    if expanded and expanded != f"${variable}":
        return expanded
    return None


def _variable_path(session: Any, path: str) -> str:
    os_mod = session.connection.modules.os
    normalized_path = os_mod.path.normcase(os_mod.path.abspath(path))
    for variable in ("JOB", "HIP"):
        base = _expanded_env_path(session, variable)
        if not base:
            continue
        normalized_base = os_mod.path.normcase(os_mod.path.abspath(base))
        try:
            common = os_mod.path.commonpath([normalized_base, normalized_path])
        except Exception:
            continue
        if common != normalized_base:
            continue
        rel = os_mod.path.relpath(path, base).replace("\\", "/")
        return f"${variable}/{rel}" if rel != "." else f"${variable}"
    return path


def _default_export_path(session: Any, node: Any, mode: str) -> str:
    os_mod = session.connection.modules.os
    base = _expanded_env_path(session, "JOB") or _expanded_env_path(session, "HIP")
    if not base:
        base = localize(session.connection.modules.tempfile.gettempdir())
    directory = os_mod.path.join(base, "tex", "cli_images")
    extension = "exr" if mode == "raw" else "png"
    frame = int(round(float(localize(session.hou.frame()))))
    stem = _sanitized_name(localize(node.name()), fallback="cop")
    candidate = os_mod.path.join(directory, f"{stem}_{mode}_f{frame:04d}.{extension}")
    root, ext = os_mod.path.splitext(candidate)
    output_path = candidate
    index = 1
    while os_mod.path.exists(output_path):
        output_path = f"{root}_{index}{ext}"
        index += 1
    return output_path


def _expand_image_path(session: Any, path: str) -> str:
    os_mod = session.connection.modules.os
    path_for_expand = os.path.abspath(path) if "$" not in path and not os.path.isabs(path) else path
    expanded = localize(session.hou.expandString(path_for_expand))
    return os_mod.path.abspath(expanded)


def _file_payload(session: Any, path: str) -> dict[str, Any]:
    os_mod = session.connection.modules.os
    return {
        "path": path,
        "variable_path": _variable_path(session, path),
        "size": int(os_mod.path.getsize(path)) if os_mod.path.exists(path) else None,
    }


def _output_names_payload(node: Any) -> list[dict[str, Any]]:
    output_names = list(localize(node.outputNames()))
    output_labels = list(localize(node.outputLabels()))
    output_types = [str(localize(value)) for value in node.outputDataTypes()]
    return [
        {
            "index": index,
            "name": output_names[index],
            "label": output_labels[index] if index < len(output_labels) else "",
            "data_type": output_types[index] if index < len(output_types) else "",
        }
        for index in range(len(output_names))
    ]


def _camera_payload(layer: Any) -> dict[str, Any]:
    return {
        "camera_position": list(localize(layer.cameraPosition())),
        "projection": str(layer.projection()),
        "focal_length": float(localize(layer.focalLength())),
        "aperture": float(localize(layer.aperture())),
        "clipping_range": list(localize(layer.clippingRange())),
    }


def handle_info(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        if not hasattr(node, "layer"):
            raise ValueError(f"Node does not provide Copernicus layer data: {args.node_path}")

        layer_node, layer_index, identity = _resolve_layer_target(node, args.output)
        layer = layer_node.layer(layer_index)

        return success_result(
            {
                "node_path": localize(node.path()),
                "layer_node_path": localize(layer_node.path()),
                **identity,
                **_layer_payload(layer),
                "camera": _camera_payload(layer),
            }
        )


def handle_sample(args: argparse.Namespace) -> dict:
    points = _normalize_points(args)
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        if not hasattr(node, "layer"):
            raise ValueError(f"Node does not provide Copernicus layer data: {args.node_path}")

        layer_node, layer_index, identity = _resolve_layer_target(node, args.output)
        layer = layer_node.layer(layer_index)

        return success_result(
            {
                "node_path": localize(node.path()),
                "layer_node_path": localize(layer_node.path()),
                **identity,
                **_layer_payload(layer),
                "samples": [_sample_point(layer, point["x"], point["y"]) for point in points],
            }
        )


def handle_export_image(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        os_mod = session.connection.modules.os
        node = get_node(session, args.node_path)
        if not hasattr(node, "layer"):
            raise ValueError(f"Node does not provide Copernicus layer data: {args.node_path}")

        layer_node, layer_index, identity = _resolve_layer_target(node, args.aov)
        layer = layer_node.layer(layer_index)
        output_path = _expand_image_path(session, args.output) if args.output else _default_export_path(session, node, args.mode)
        os_mod.makedirs(os_mod.path.dirname(output_path), exist_ok=True)

        parent = layer_node.parent()
        rop_name = _unique_child_name(parent, "_houdini_cli_export_image")
        rop = parent.createNode("rop_image", rop_name)
        try:
            _set_parm(rop, "coppath", localize(layer_node.path()))
            _set_parm(rop, "copoutput", output_path)
            _set_menu_parm(rop, "colorconversion", "raw" if args.mode == "raw" else "bakeocio")
            _set_parm(rop, "mkpath", 1, required=False)
            _set_parm(rop, "outputaovs", 1, required=False)
            _set_parm(rop, "aov1", "C", required=False)
            if localize(layer_node.path()) == localize(node.path()):
                _set_parm(rop, "useport1", 1, required=False)
                _set_parm(rop, "port1", int(identity["output_index"]), required=False)
            if args.mode == "view":
                if args.display:
                    _set_parm(rop, "ociodisplay", args.display, required=False)
                if args.view:
                    _set_parm(rop, "ocioview", args.view, required=False)
            _press_button(rop, "execute")
        finally:
            rop.destroy()

        if not os_mod.path.exists(output_path):
            raise RuntimeError(f"ROP Image did not create the expected file: {output_path}")

        return success_result(
            {
                "node_path": localize(node.path()),
                "layer_node_path": localize(layer_node.path()),
                **identity,
                "mode": args.mode,
                "file": _file_payload(session, output_path),
                "resolution": _layer_payload(layer)["resolution"],
                "color_conversion": {
                    "mode": "raw" if args.mode == "raw" else "bakeocio",
                    "display": args.display or "Default",
                    "view": args.view or "Default",
                },
                "orientation": {
                    "file_arrays": "top-origin in common external tools",
                    "houdini_pixels": "Houdini COP pixel comparisons may need Y-coordinate mapping",
                },
            }
        )


def handle_import_image(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        os_mod = session.connection.modules.os
        parent = get_node(session, args.parent)
        image_path = _expand_image_path(session, args.image_path)
        if not os_mod.path.exists(image_path):
            raise ValueError(f"Image file not found: {args.image_path}")

        base_name = args.name or f"cli_image_{_sanitized_name(os_mod.path.splitext(os_mod.path.basename(image_path))[0], fallback='image')}"
        node_name = _unique_child_name(parent, _sanitized_name(base_name, fallback="cli_image"))
        file_node = parent.createNode("file", node_name)
        variable_path = _variable_path(session, image_path)
        _set_parm(file_node, "filename", variable_path)
        _set_menu_parm(file_node, "colorspace", args.colorspace)
        reload_pressed = _press_button(file_node, "reload")
        addaovs_pressed = _press_button(file_node, "addaovs")
        if args.set_display:
            file_node.setDisplayFlag(True)
            try:
                file_node.setRenderFlag(True)
            except Exception:
                pass

        layer_payload: dict[str, Any] | None = None
        try:
            layer_payload = _layer_payload(file_node.layer())
        except Exception:
            layer_payload = None

        return success_result(
            {
                "node_path": localize(file_node.path()),
                "parent_path": localize(parent.path()),
                "file": {
                    **_file_payload(session, image_path),
                    "parameter_value": variable_path,
                },
                "colorspace": args.colorspace,
                "reload_pressed": reload_pressed,
                "addaovs_pressed": addaovs_pressed,
                "outputs": _output_names_payload(file_node),
                "layer": layer_payload,
                "display": bool(args.set_display),
            }
        )
