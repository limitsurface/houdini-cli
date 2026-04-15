"""Copernicus commands."""

from __future__ import annotations

import argparse
import math
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


def _resolve_output_index(node: Any, output_ref: str) -> int:
    try:
        return int(output_ref)
    except ValueError:
        pass

    output_names = list(localize(node.outputNames()))
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


def _find_output_proxy_node(node: Any, output_index: int) -> Any | None:
    for child in list(node.outputs()):
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


def _resolve_layer_target(node: Any, output_ref: str | None) -> tuple[Any, dict[str, Any]]:
    output_names = list(localize(node.outputNames()))
    if output_ref is not None or len(output_names) > 1:
        resolved_ref = output_ref if output_ref is not None else "0"
        output_index = _resolve_output_index(node, resolved_ref)
        identity = {
            "source_node_path": localize(node.path()),
            **_output_identity(node, output_index),
        }
        if len(output_names) == 1 and output_index == 0:
            return node, identity
        proxy = _find_output_proxy_node(node, output_index)
        if proxy is not None:
            return proxy, identity
        return node, identity

    upstream = _first_input_connection(node)
    if upstream is not None and upstream.inputNode() is not None:
        source_node = upstream.inputNode()
        identity = {
            "source_node_path": localize(source_node.path()),
            **_connection_output_identity(upstream),
        }
        return node, identity

    identity = {
        "source_node_path": localize(node.path()),
        **_output_identity(node, 0),
    }
    return node, identity


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

        layer_node, identity = _resolve_layer_target(node, args.output)
        layer = layer_node.layer()

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

        layer_node, identity = _resolve_layer_target(node, args.output)
        layer = layer_node.layer()

        return success_result(
            {
                "node_path": localize(node.path()),
                "layer_node_path": localize(layer_node.path()),
                **identity,
                **_layer_payload(layer),
                "samples": [_sample_point(layer, point["x"], point["y"]) for point in points],
            }
        )
