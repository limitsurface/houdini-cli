"""Geometry attribute inspection commands."""

from __future__ import annotations

import argparse
import statistics
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .node_common import get_node

DEFAULT_LIMIT = 10
VALID_CLASSES = ("point", "prim", "vertex", "detail")
VALID_STATS = ("min", "max", "mean", "median")


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    attrib_parser = subparsers.add_parser("attrib", help="Inspect cooked geometry attributes.")
    attrib_subparsers = attrib_parser.add_subparsers(dest="attrib_command", required=True)

    list_parser = attrib_subparsers.add_parser("list", help="List geometry attributes on a node.")
    list_parser.add_argument("node_path", help="Geometry-producing node path.")
    list_parser.add_argument(
        "--class",
        dest="attrib_class",
        choices=VALID_CLASSES,
        help="Filter to one attribute class.",
    )
    list_parser.set_defaults(handler=handle_list)

    get_parser = attrib_subparsers.add_parser("get", help="Inspect one geometry attribute.")
    get_parser.add_argument("node_path", help="Geometry-producing node path.")
    get_parser.add_argument("attrib_name", help="Attribute name to inspect.")
    get_parser.add_argument(
        "--class",
        dest="attrib_class",
        choices=VALID_CLASSES,
        required=True,
        help="Attribute class to inspect.",
    )
    get_parser.add_argument(
        "--element",
        type=int,
        help="Explicit element index to inspect.",
    )
    get_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum sampled elements when --element is omitted (default: {DEFAULT_LIMIT}).",
    )
    get_parser.add_argument(
        "--stats",
        help="Comma-separated numeric stats: min,max,mean,median",
    )
    get_parser.set_defaults(handler=handle_get)


def _get_geometry(node: Any) -> Any:
    try:
        geometry = node.geometry()
    except Exception as exc:  # pragma: no cover - depends on live HOM behavior
        raise ValueError(f"Node does not provide cooked geometry: {localize(node.path())}") from exc

    if geometry is None:
        raise ValueError(f"Node does not provide cooked geometry: {localize(node.path())}")
    return geometry


def _class_accessor(attrib_class: str) -> tuple[str, str]:
    mapping = {
        "point": ("pointAttribs", "findPointAttrib"),
        "prim": ("primAttribs", "findPrimAttrib"),
        "vertex": ("vertexAttribs", "findVertexAttrib"),
        "detail": ("globalAttribs", "findGlobalAttrib"),
    }
    return mapping[attrib_class]


def _normalize_data_type(attrib: Any) -> str:
    text = str(attrib.dataType())
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text.lower()


def _attrib_definition(attrib: Any, attrib_class: str) -> dict:
    definition = {
        "name": str(attrib.name()),
        "class": attrib_class,
        "size": int(attrib.size()),
        "data_type": _normalize_data_type(attrib),
    }
    if hasattr(attrib, "isArrayType"):
        definition["array"] = bool(attrib.isArrayType())
    return definition


def _get_attrib(geometry: Any, attrib_class: str, attrib_name: str) -> Any:
    _, find_name = _class_accessor(attrib_class)
    attrib = getattr(geometry, find_name)(attrib_name)
    if attrib is None:
        raise ValueError(f"Attribute not found: class={attrib_class} name={attrib_name}")
    return attrib


def _element_count(geometry: Any, attrib_class: str) -> int:
    if attrib_class == "point":
        return int(geometry.pointCount())
    if attrib_class == "prim":
        return int(geometry.primCount())
    if attrib_class == "vertex":
        return int(geometry.vertexCount())
    return 1


def _vertex_at(geometry: Any, index: int) -> Any:
    current = 0
    for prim in geometry.iterPrims():
        for vertex in prim.vertices():
            if current == index:
                return vertex
            current += 1
    raise ValueError(f"Vertex index out of range: {index}")


def _element_at(geometry: Any, attrib_class: str, index: int) -> Any:
    if index < 0:
        raise ValueError(f"Element index must be non-negative: {index}")
    if attrib_class == "point":
        count = _element_count(geometry, attrib_class)
        if index >= count:
            raise ValueError(f"Point index out of range: {index}")
        return geometry.iterPoints()[index]
    if attrib_class == "prim":
        count = _element_count(geometry, attrib_class)
        if index >= count:
            raise ValueError(f"Primitive index out of range: {index}")
        return geometry.iterPrims()[index]
    if attrib_class == "vertex":
        return _vertex_at(geometry, index)
    raise ValueError("Detail attributes do not accept --element")


def _sample_elements(geometry: Any, attrib_class: str, limit: int) -> list[tuple[int, Any]]:
    if limit <= 0:
        raise ValueError(f"Limit must be positive: {limit}")

    if attrib_class == "point":
        sampled: list[tuple[int, Any]] = []
        for index, point in enumerate(geometry.iterPoints()):
            sampled.append((index, point))
            if len(sampled) >= limit:
                return sampled
        return sampled
    if attrib_class == "prim":
        sampled = []
        for index, prim in enumerate(geometry.iterPrims()):
            sampled.append((index, prim))
            if len(sampled) >= limit:
                return sampled
        return sampled
    if attrib_class == "vertex":
        sampled: list[tuple[int, Any]] = []
        current = 0
        for prim in geometry.iterPrims():
            for vertex in prim.vertices():
                sampled.append((current, vertex))
                current += 1
                if len(sampled) >= limit:
                    return sampled
        return sampled
    return [(0, geometry)]


def _value_from_element(element: Any, attrib: Any) -> Any:
    return localize(element.attribValue(attrib))


def _all_values(geometry: Any, attrib_class: str, attrib: Any) -> list[Any]:
    return [_value_from_element(element, attrib) for _, element in _sample_elements(geometry, attrib_class, _element_count(geometry, attrib_class))]


def _normalize_numeric_sample(value: Any) -> list[float]:
    if isinstance(value, bool):
        return [float(value)]
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)) and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value):
        return [float(item) for item in value]
    raise ValueError("Stats are only supported for numeric attributes")


def _compute_stats(values: list[Any], requested_stats: list[str]) -> dict:
    numeric_values = [_normalize_numeric_sample(value) for value in values]
    if not numeric_values:
        return {}

    width = len(numeric_values[0])
    for sample in numeric_values:
        if len(sample) != width:
            raise ValueError("Stats require a consistent numeric tuple size")

    stats: dict[str, Any] = {}
    for stat_name in requested_stats:
        components = []
        for component_index in range(width):
            component_values = [sample[component_index] for sample in numeric_values]
            if stat_name == "min":
                components.append(min(component_values))
            elif stat_name == "max":
                components.append(max(component_values))
            elif stat_name == "mean":
                components.append(statistics.fmean(component_values))
            else:
                components.append(statistics.median(component_values))
        stats[stat_name] = components[0] if width == 1 else components
    return stats


def _parse_stats(raw_stats: str | None) -> list[str]:
    if not raw_stats:
        return []

    requested_stats = []
    for raw_name in raw_stats.split(","):
        name = raw_name.strip().lower()
        if not name:
            continue
        if name not in VALID_STATS:
            raise ValueError(f"Unsupported stat: {name}")
        if name not in requested_stats:
            requested_stats.append(name)
    return requested_stats


def handle_list(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        geometry = _get_geometry(node)

        classes = [args.attrib_class] if args.attrib_class else list(VALID_CLASSES)
        data = {"node": args.node_path, "classes": {}}
        for attrib_class in classes:
            list_name, _ = _class_accessor(attrib_class)
            attribs = getattr(geometry, list_name)()
            data["classes"][attrib_class] = [_attrib_definition(attrib, attrib_class) for attrib in attribs]

        return success_result(data)


def handle_get(args: argparse.Namespace) -> dict:
    requested_stats = _parse_stats(args.stats)

    with connect(args.host, args.port) as session:
        node = get_node(session, args.node_path)
        geometry = _get_geometry(node)
        attrib = _get_attrib(geometry, args.attrib_class, args.attrib_name)
        count = _element_count(geometry, args.attrib_class)

        data = {
            "node": args.node_path,
            "attribute": _attrib_definition(attrib, args.attrib_class),
        }

        meta: dict[str, Any] | None = None

        if args.attrib_class == "detail":
            if args.element is not None:
                raise ValueError("Detail attributes do not accept --element")
            values = [localize(geometry.attribValue(attrib))]
            data["value"] = values[0]
        elif args.element is not None:
            element = _element_at(geometry, args.attrib_class, args.element)
            data["value"] = {
                "element": args.element,
                "value": _value_from_element(element, attrib),
            }
            values = [data["value"]["value"]]
        else:
            sampled = _sample_elements(geometry, args.attrib_class, args.limit)
            data["values"] = [
                {"element": index, "value": _value_from_element(element, attrib)}
                for index, element in sampled
            ]
            values = [item["value"] for item in data["values"]]
            meta = {
                "limit": args.limit,
                "truncated": count > args.limit,
                "total_elements": count,
            }

        if requested_stats:
            stats_values = values if args.element is not None or args.attrib_class == "detail" else _all_values(
                geometry, args.attrib_class, attrib
            )
            data["stats"] = _compute_stats(stats_values, requested_stats)

        return success_result(data, meta=meta)
