"""HDA validation commands."""

from __future__ import annotations

import argparse
import re
from typing import Any

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .hda_common import definition_for_node
from .node_common import get_node

_CHANNEL_REF_PATTERN = re.compile(r"\bch(?:s|f|i|v|p|raw)?\s*\(\s*['\"]([^'\"]+)['\"]")


def _node_messages(node: Any) -> dict[str, list[str]]:
    return {
        "errors": [localize(value) for value in node.errors()],
        "warnings": [localize(value) for value in node.warnings()],
        "messages": [localize(value) for value in node.messages()],
    }


def _temporary_name(parent: Any) -> str:
    base = "__hda_validate_tmp"
    name = base
    suffix = 1
    while parent.node(name) is not None:
        name = f"{base}{suffix}"
        suffix += 1
    return name


def _within_node_root(node_path: str, root_path: str) -> bool:
    root = root_path.rstrip("/")
    return node_path == root or node_path.startswith(root + "/")


def _parm_node_path(parm_path: str) -> str:
    return parm_path.rsplit("/", 1)[0]


def _safe_raw_value(parm: Any) -> Any:
    for method in ("rawValue", "unexpandedString"):
        if not hasattr(parm, method):
            continue
        try:
            return localize(getattr(parm, method)())
        except Exception:
            continue
    try:
        return localize(parm.valueAsData())
    except Exception:
        return None


def _safe_expression(parm: Any) -> tuple[str | None, str | None]:
    try:
        return (
            localize(parm.expression()),
            str(localize(parm.expressionLanguage().name())).lower(),
        )
    except Exception:
        return None, None


def _target_paths_from_hom(parm: Any) -> list[str]:
    paths: list[str] = []
    for owner in (parm, getattr(parm, "tuple", lambda: None)()):
        if owner is None or not hasattr(owner, "references"):
            continue
        try:
            paths.extend(localize(target.path()) for target in owner.references())
        except Exception:
            continue
    return paths


def _resolve_channel_ref(session: Any, source_node: Any, token: str) -> str | None:
    if token.startswith("/"):
        target = session.hou.parm(token)
        return localize(target.path()) if target is not None else None
    if "/" not in token:
        target = source_node.parm(token)
        return localize(target.path()) if target is not None else None
    node_token, parm_name = token.rsplit("/", 1)
    target_node = source_node.node(node_token)
    if target_node is None:
        return None
    target = target_node.parm(parm_name)
    return localize(target.path()) if target is not None else None


def _resolved_channel_targets(session: Any, parm: Any, raw: Any, expression: str | None) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for path in _target_paths_from_hom(parm):
        if path in seen:
            continue
        seen.add(path)
        rows.append({"target": path, "source": "hom", "token": path})

    for text in (expression, raw if isinstance(raw, str) else None):
        if not text:
            continue
        for match in _CHANNEL_REF_PATTERN.finditer(text):
            token = match.group(1)
            target = _resolve_channel_ref(session, parm.node(), token)
            if target is None or target in seen:
                continue
            seen.add(target)
            rows.append({"target": target, "source": "expression", "token": token})
    return rows


def _contained_nodes(node: Any) -> list[Any]:
    try:
        return [node, *list(node.allSubChildren())]
    except Exception:
        return [node]


def _external_reference_rows(session: Any, asset_node: Any) -> dict[str, Any]:
    root_path = localize(asset_node.path())
    external: list[dict[str, Any]] = []
    absolute_internal: list[dict[str, Any]] = []
    all_refs: list[dict[str, Any]] = []

    for node in _contained_nodes(asset_node):
        for parm in node.parms():
            raw = _safe_raw_value(parm)
            expression, language = _safe_expression(parm)
            targets = _resolved_channel_targets(session, parm, raw, expression)
            if not targets:
                continue
            from_parm = localize(parm.path())
            from_node = localize(node.path())
            for target in targets:
                target_path = str(target["target"])
                target_node = _parm_node_path(target_path)
                external_ref = not _within_node_root(target_node, root_path)
                absolute_internal_ref = (
                    not external_ref
                    and str(target.get("token", "")).startswith("/")
                    and _within_node_root(target_node, root_path)
                )
                row = {
                    "from_node": from_node,
                    "from_parm": from_parm,
                    "to_parm": target_path,
                    "external": external_ref,
                    "absolute": str(target.get("token", "")).startswith("/"),
                    "token": target.get("token"),
                    "source": target.get("source"),
                    "raw": raw,
                    "expression": expression,
                    "language": language,
                    "severity": "error" if external_ref else "warning" if absolute_internal_ref else "info",
                }
                all_refs.append(row)
                if external_ref:
                    external.append(row)
                elif absolute_internal_ref:
                    absolute_internal.append(row)

    return {
        "root": root_path,
        "count": len(external),
        "items": external,
        "absolute_internal_count": len(absolute_internal),
        "absolute_internal": absolute_internal,
        "internal_count": len(all_refs) - len(external) - len(absolute_internal),
        "reference_count": len(all_refs),
    }


_EXTERNAL_REFERENCE_AUDIT_CODE = r"""
import re
import hou

CHANNEL_REF_PATTERN = re.compile(r"\bch(?:s|f|i|v|p|raw)?\s*\(\s*['\"]([^'\"]+)['\"]")

def _houdini_cli_within_node_root(node_path, root_path):
    root = root_path.rstrip("/")
    return node_path == root or node_path.startswith(root + "/")

def _houdini_cli_parm_node_path(parm_path):
    return parm_path.rsplit("/", 1)[0]

def _houdini_cli_raw(parm):
    for method in ("rawValue", "unexpandedString"):
        if hasattr(parm, method):
            try:
                return getattr(parm, method)()
            except Exception:
                pass
    try:
        return parm.valueAsData()
    except Exception:
        return None

def _houdini_cli_expression(parm):
    try:
        return parm.expression(), parm.expressionLanguage().name().lower()
    except Exception:
        return None, None

def _houdini_cli_target_paths(parm):
    paths = []
    for owner in (parm, parm.tuple()):
        if not hasattr(owner, "references"):
            continue
        try:
            paths.extend(target.path() for target in owner.references())
        except Exception:
            pass
    return paths

def _houdini_cli_resolve_channel_ref(source_node, token):
    if token.startswith("/"):
        target = hou.parm(token)
        return target.path() if target is not None else None
    if "/" not in token:
        target = source_node.parm(token)
        return target.path() if target is not None else None
    node_token, parm_name = token.rsplit("/", 1)
    target_node = source_node.node(node_token)
    if target_node is None:
        return None
    target = target_node.parm(parm_name)
    return target.path() if target is not None else None

def _houdini_cli_channel_targets(parm, raw, expression):
    seen = set()
    rows = []
    for path in _houdini_cli_target_paths(parm):
        if path in seen:
            continue
        seen.add(path)
        rows.append({"target": path, "source": "hom", "token": path})
    for text in (expression, raw if isinstance(raw, str) else None):
        if not text:
            continue
        for match in CHANNEL_REF_PATTERN.finditer(text):
            token = match.group(1)
            target = _houdini_cli_resolve_channel_ref(parm.node(), token)
            if target is None or target in seen:
                continue
            seen.add(target)
            rows.append({"target": target, "source": "expression", "token": token})
    return rows

def _houdini_cli_hda_external_reference_audit(asset_path):
    asset_node = hou.node(asset_path)
    if asset_node is None:
        raise ValueError("Node not found: " + asset_path)
    root_path = asset_node.path()
    external = []
    absolute_internal = []
    all_refs = []
    try:
        nodes = [asset_node] + list(asset_node.allSubChildren())
    except Exception:
        nodes = [asset_node]
    for node in nodes:
        for parm in node.parms():
            raw = _houdini_cli_raw(parm)
            expression, language = _houdini_cli_expression(parm)
            targets = _houdini_cli_channel_targets(parm, raw, expression)
            if not targets:
                continue
            for target in targets:
                target_path = target["target"]
                target_node = _houdini_cli_parm_node_path(target_path)
                external_ref = not _houdini_cli_within_node_root(target_node, root_path)
                absolute_internal_ref = (
                    not external_ref
                    and str(target.get("token", "")).startswith("/")
                    and _houdini_cli_within_node_root(target_node, root_path)
                )
                row = {
                    "from_node": node.path(),
                    "from_parm": parm.path(),
                    "to_parm": target_path,
                    "external": external_ref,
                    "absolute": str(target.get("token", "")).startswith("/"),
                    "token": target.get("token"),
                    "source": target.get("source"),
                    "raw": raw,
                    "expression": expression,
                    "language": language,
                    "severity": "error" if external_ref else "warning" if absolute_internal_ref else "info",
                }
                all_refs.append(row)
                if external_ref:
                    external.append(row)
                elif absolute_internal_ref:
                    absolute_internal.append(row)
    return {
        "root": root_path,
        "count": len(external),
        "items": external,
        "absolute_internal_count": len(absolute_internal),
        "absolute_internal": absolute_internal,
        "internal_count": len(all_refs) - len(external) - len(absolute_internal),
        "reference_count": len(all_refs),
    }
"""


def _external_references_in_houdini(session: Any, asset_node: Any) -> dict[str, Any]:
    if not hasattr(session, "connection"):
        return _external_reference_rows(session, asset_node)
    asset_path = localize(asset_node.path())
    session.connection.execute(_EXTERNAL_REFERENCE_AUDIT_CODE)
    return localize(
        session.connection.eval(f"_houdini_cli_hda_external_reference_audit({asset_path!r})")
    )


def validate_asset(
    session: Any,
    node: Any,
    *,
    fresh: bool,
    cook: bool,
    frames: list[float],
    external_references: bool = False,
) -> dict[str, Any]:
    definition = definition_for_node(node)
    result = {
        "definition_current": bool(localize(definition.isCurrent())),
        "locked": bool(localize(node.isLockedHDA())),
        "matches": bool(localize(node.matchesCurrentDefinition())),
        "library": localize(definition.libraryFilePath()),
    }
    target = node
    temporary = None
    if fresh:
        parent = node.parent()
        temporary = parent.createNode(localize(node.type().name()), _temporary_name(parent))
        for index, source in enumerate(node.inputs()):
            if source is not None:
                temporary.setInput(index, source)
        target = temporary
        result["fresh_instance"] = localize(target.path())
    original_frame = float(localize(session.hou.frame()))
    try:
        frame_results = []
        for frame in frames or ([original_frame] if cook else []):
            session.hou.setFrame(frame)
            target.cook(force=True)
            frame_results.append({"frame": frame, **_node_messages(target)})
        result["frames"] = frame_results
        result["parms"] = len(target.parms())
        result["input_count"] = len([item for item in target.inputs() if item is not None])
        result["output_count"] = len(target.outputs())
        result["compress"] = (
            bool(localize(target.isGenericFlagSet(session.hou.nodeFlag.Compress)))
            if hasattr(target, "isGenericFlagSet")
            else None
        )
        if external_references:
            result["external_references"] = _external_references_in_houdini(session, target)
            result["ok"] = result["external_references"]["count"] == 0
    finally:
        session.hou.setFrame(original_frame)
        if temporary is not None:
            temporary.destroy()
    return result


def handle_validate(args: argparse.Namespace) -> dict:
    frames = [float(value) for value in args.frames.split(",")] if args.frames else []
    with connect(args.host, args.port) as session:
        result = validate_asset(
            session,
            get_node(session, args.asset_node),
            fresh=args.fresh_instance,
            cook=args.cook or bool(frames),
            frames=frames,
            external_references=args.external_references or args.strict,
        )
        warnings = [warning for row in result.get("frames", []) for warning in row["warnings"]]
        if args.strict and warnings:
            raise ValueError(f"Validation warnings: {warnings}")
        external_count = result.get("external_references", {}).get("count", 0)
        if args.strict and external_count:
            raise ValueError(f"External HDA parameter references: {external_count}")
        return success_result(result)
