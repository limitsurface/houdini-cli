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


def handle_sample(args: argparse.Namespace) -> dict:
    points = _normalize_points(args)
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        if not hasattr(node, "layer"):
            raise ValueError(f"Node does not provide Copernicus layer data: {args.node_path}")

        output_index = _resolve_output_index(node, args.output)
        output_names = list(localize(node.outputNames()))
        output_labels = list(localize(node.outputLabels()))
        layer = node.layer(output_index)

        return success_result(
            {
                "node_path": localize(node.path()),
                "output_index": output_index,
                "output_name": output_names[output_index],
                "output_label": output_labels[output_index],
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
                "samples": [_sample_point(layer, point["x"], point["y"]) for point in points],
            }
        )
