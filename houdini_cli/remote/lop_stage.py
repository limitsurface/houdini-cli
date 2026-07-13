"""Houdini-side USD stage summary helpers."""

from __future__ import annotations

from .module import RemoteModule


LOP_STAGE_SOURCE = r'''
def _houdini_cli_lop_path_bucket(limit):
    return {"count": 0, "paths": [], "returned": 0, "truncated": False, "limit": limit}


def _houdini_cli_lop_add_path(bucket, path):
    bucket["count"] += 1
    if len(bucket["paths"]) < bucket["limit"]:
        bucket["paths"].append(str(path))
        bucket["returned"] += 1
    else:
        bucket["truncated"] = True


def _houdini_cli_lop_has_collection(prim):
    try:
        return any(str(schema).startswith("CollectionAPI:") for schema in prim.GetAppliedSchemas())
    except Exception:
        return False


def _houdini_cli_lop_active_settings(stage, UsdRender):
    try:
        settings = UsdRender.Settings.GetStageRenderSettings(stage)
        if settings and settings.GetPrim().IsValid():
            return settings
    except Exception:
        pass
    try:
        path = stage.GetMetadata("renderSettingsPrimPath")
        if path:
            settings = UsdRender.Settings.Get(stage, path)
            if settings and settings.GetPrim().IsValid():
                return settings
    except Exception:
        pass
    return None


def _houdini_cli_lop_stage_summary(node_path, output_index, max_depth, max_prims, top_types, include_paths, path_limit):
    import time
    import hou
    from pxr import Usd, UsdGeom, UsdLux, UsdRender, UsdShade

    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)
    category = str(node.type().category().name())
    if category != "Lop":
        raise ValueError("Node is not a LOP: " + node_path + " (category: " + category + ")")

    output_counts = []
    for method_name in ("outputNames", "outputConnectors"):
        try:
            output_counts.append(len(getattr(node, method_name)()))
        except Exception:
            pass
    output_count = max([1] + output_counts)
    if output_index < 0 or output_index >= output_count:
        raise ValueError(
            "Output index out of range for " + node_path + ": " + str(output_index)
            + " (output count: " + str(output_count) + ")"
        )

    cook_count_before = int(node.cookCount())
    needed_cook_before = bool(node.needsToCook())
    acquire_started = time.perf_counter()
    stage = node.stage(output_index=output_index)
    acquire_seconds = time.perf_counter() - acquire_started
    cook_count_after = int(node.cookCount())
    if stage is None:
        raise ValueError("LOP node did not provide a stage: " + node_path)

    path_keys = (
        "top_level", "cameras", "lights", "materials", "render_settings",
        "render_products", "prototypes", "composition_arcs",
    )
    paths = {key: _houdini_cli_lop_path_bucket(path_limit) for key in path_keys}
    counts = {
        "prims": 0,
        "active": 0,
        "inactive": 0,
        "instances": 0,
        "prototypes": 0,
        "materials": 0,
        "lights": 0,
        "cameras": 0,
        "render_settings": 0,
        "render_products": 0,
        "collections": 0,
    }
    references = 0
    payloads = 0
    type_counts = {}
    truncated = False

    traverse_started = time.perf_counter()
    prim_range = Usd.PrimRange.Stage(stage, Usd.PrimAllPrimsPredicate)
    iterator = iter(prim_range)
    for prim in iterator:
        path = prim.GetPath()
        depth = int(path.pathElementCount)
        if max_depth is not None and depth > max_depth:
            iterator.PruneChildren()
            continue
        if counts["prims"] >= max_prims:
            truncated = True
            break

        counts["prims"] += 1
        active = bool(prim.IsActive())
        counts["active" if active else "inactive"] += 1
        if prim.IsInstance():
            counts["instances"] += 1

        type_name = str(prim.GetTypeName()) or "<untyped>"
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

        is_camera = bool(prim.IsA(UsdGeom.Camera))
        is_material = bool(prim.IsA(UsdShade.Material))
        is_render_settings = bool(prim.IsA(UsdRender.Settings))
        is_render_product = bool(prim.IsA(UsdRender.Product))
        try:
            is_light = bool(prim.HasAPI(UsdLux.LightAPI))
        except Exception:
            is_light = False

        if is_camera:
            counts["cameras"] += 1
        if is_material:
            counts["materials"] += 1
        if is_light:
            counts["lights"] += 1
        if is_render_settings:
            counts["render_settings"] += 1
        if is_render_product:
            counts["render_products"] += 1
        if _houdini_cli_lop_has_collection(prim):
            counts["collections"] += 1

        has_reference = bool(prim.HasAuthoredReferences())
        has_payload = bool(prim.HasAuthoredPayloads())
        references += int(has_reference)
        payloads += int(has_payload)

        if include_paths:
            if depth == 1:
                _houdini_cli_lop_add_path(paths["top_level"], path)
            if is_camera:
                _houdini_cli_lop_add_path(paths["cameras"], path)
            if is_light:
                _houdini_cli_lop_add_path(paths["lights"], path)
            if is_material:
                _houdini_cli_lop_add_path(paths["materials"], path)
            if is_render_settings:
                _houdini_cli_lop_add_path(paths["render_settings"], path)
            if is_render_product:
                _houdini_cli_lop_add_path(paths["render_products"], path)
            if has_reference or has_payload:
                _houdini_cli_lop_add_path(paths["composition_arcs"], path)

        if max_depth is not None and depth >= max_depth:
            iterator.PruneChildren()

    prototypes = list(stage.GetPrototypes())
    counts["prototypes"] = len(prototypes)
    if include_paths:
        for prototype in prototypes:
            _houdini_cli_lop_add_path(paths["prototypes"], prototype.GetPath())

    traverse_seconds = time.perf_counter() - traverse_started
    ordered_types = sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    shown_types = ordered_types[:top_types]
    type_other = sum(count for _, count in ordered_types[top_types:])

    default_prim = stage.GetDefaultPrim()
    default_prim_path = str(default_prim.GetPath()) if default_prim and default_prim.IsValid() else None
    active_settings = _houdini_cli_lop_active_settings(stage, UsdRender)
    active_settings_path = None
    active_camera_path = None
    if active_settings is not None:
        active_settings_path = str(active_settings.GetPath())
        try:
            targets = active_settings.GetCameraRel().GetTargets()
            if targets:
                active_camera_path = str(targets[0])
        except Exception:
            pass

    root_layer = stage.GetRootLayer()
    data = {
        "node_path": str(node.path()),
        "output": output_index,
        "stage": {
            "default_prim": default_prim_path,
            "up_axis": str(UsdGeom.GetStageUpAxis(stage)),
            "meters_per_unit": float(UsdGeom.GetStageMetersPerUnit(stage)),
            "time_codes_per_second": float(stage.GetTimeCodesPerSecond()),
            "root_layer": str(root_layer.identifier) if root_layer else None,
        },
        "counts": counts,
        "type_histogram": [{"type": name, "count": count} for name, count in shown_types],
        "type_histogram_other": type_other,
        "active_render_settings": active_settings_path,
        "active_camera": active_camera_path,
        "composition": {
            "references": references,
            "payloads": payloads,
            "sublayers": len(root_layer.subLayerPaths) if root_layer else 0,
        },
        "timings": {
            "stage_acquisition_seconds": acquire_seconds,
            "traversal_seconds": traverse_seconds,
        },
        "cook": {
            "occurred": cook_count_after > cook_count_before,
            "needed_before": needed_cook_before,
            "count_before": cook_count_before,
            "count_after": cook_count_after,
        },
        "meta": {
            "truncated": truncated,
            "counts_complete": not truncated,
            "max_depth": max_depth,
            "max_prims": max_prims,
            "visited_prims": counts["prims"],
            "top_types": top_types,
            "included_paths": include_paths,
            "path_limit": path_limit if include_paths else None,
            "instance_proxies": "excluded",
        },
    }
    if include_paths:
        data["paths"] = paths
    return data
'''


LOP_STAGE_REMOTE = RemoteModule(
    namespace="lop_stage",
    source=LOP_STAGE_SOURCE,
    entrypoints={"summary": "_houdini_cli_lop_stage_summary"},
)
