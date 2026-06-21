"""Shared parameter search and reference inspection."""

from __future__ import annotations

import re
from typing import Any

from ..transport.rpyc import localize

CHANNEL_REF_PATTERN = re.compile(r"\bch(?:s|f|i|v|p|raw)?\s*\(\s*['\"]([^'\"]+)['\"]")
SKIPPED_TEMPLATE_TYPES = {"Button", "Folder", "FolderSet", "Label", "Separator"}


def safe_raw_value(parm: Any) -> Any:
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


def safe_expression(parm: Any) -> tuple[str | None, str | None]:
    try:
        expression = localize(parm.expression())
        language = str(localize(parm.expressionLanguage().name())).lower()
        return expression, language
    except Exception:
        return None, None


def target_paths_from_hom(parm: Any, *, include_tuple: bool = False) -> list[str]:
    owners = [parm]
    if include_tuple:
        try:
            owners.append(parm.tuple())
        except Exception:
            pass
    paths: list[str] = []
    for owner in owners:
        if owner is None or not hasattr(owner, "references"):
            continue
        try:
            paths.extend(localize(target.path()) for target in owner.references())
        except Exception:
            continue
    return paths


def resolve_channel_ref(session: Any, parm: Any, token: str) -> str | None:
    try:
        source_node = parm.node()
    except Exception:
        return None
    try:
        if token.startswith("/"):
            target = session.hou.parm(token)
        elif "/" not in token:
            target = source_node.parm(token)
        else:
            node_token, parm_name = token.rsplit("/", 1)
            target_node = source_node.node(node_token)
            target = target_node.parm(parm_name) if target_node is not None else None
    except Exception:
        return None
    return localize(target.path()) if target is not None else None


def resolved_channel_targets(
    session: Any,
    parm: Any,
    *,
    raw: Any | None = None,
    expression: str | None = None,
    include_tuple_hom: bool = False,
) -> list[dict[str, Any]]:
    if raw is None:
        raw = safe_raw_value(parm)
    if expression is None:
        expression, _language = safe_expression(parm)

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for path in target_paths_from_hom(parm, include_tuple=include_tuple_hom):
        if path in seen:
            continue
        seen.add(path)
        rows.append({"target": path, "source": "hom", "token": path})

    for text in (expression, raw if isinstance(raw, str) else None):
        if not text:
            continue
        for match in CHANNEL_REF_PATTERN.finditer(text):
            token = match.group(1)
            target = resolve_channel_ref(session, parm, token)
            if target is None or target in seen:
                continue
            seen.add(target)
            rows.append({"target": target, "source": "expression", "token": token})
    return rows


def target_paths(session: Any, parm: Any) -> list[str]:
    return [str(row["target"]) for row in resolved_channel_targets(session, parm)]


def parm_node_path(parm_path: str) -> str:
    return parm_path.rsplit("/", 1)[0]


def within_node_root(node_path: str, root_path: str) -> bool:
    root = root_path.rstrip("/")
    return node_path == root or node_path.startswith(root + "/")


def parm_within_root(parm_path: str, root_path: str) -> bool:
    return within_node_root(parm_node_path(parm_path), root_path)


def _parm_template_type(parm: Any) -> str:
    return localize(parm.parmTemplate().type().name())


def _tuple_members(parm: Any) -> list[Any]:
    return list(parm.tuple())


def _tuple_name(parm: Any) -> str:
    return localize(parm.tuple().name())


def _tuple_type_label(parm: Any) -> str:
    members = _tuple_members(parm)
    base = _parm_template_type(parm)
    return f"{base}{len(members)}" if len(members) > 1 else base


def parm_search_rows(
    session: Any,
    node: Any,
    *,
    query: str,
    include_raw: bool,
    include_expressions: bool,
    include_targets: bool,
    max_matches: int,
) -> list[dict[str, Any]]:
    needle = query.lower()
    rows = []
    seen: set[str] = set()
    for parm in node.parms():
        if _parm_template_type(parm) in SKIPPED_TEMPLATE_TYPES:
            continue
        path = localize(parm.path())
        if path in seen:
            continue
        seen.add(path)
        name = localize(parm.name())
        tuple_name = _tuple_name(parm)
        raw = safe_raw_value(parm)
        expression, language = safe_expression(parm)
        targets = target_paths(session, parm)
        haystacks = [name, tuple_name, "" if raw is None else str(raw), expression or "", *targets]
        matches = []
        if any(needle in item.lower() for item in (name, tuple_name)):
            matches.append("name")
        if raw is not None and needle in str(raw).lower():
            matches.append("raw")
        if expression and needle in expression.lower():
            matches.append("expression")
        if any(needle in target.lower() for target in targets):
            matches.append("resolved_target")
        if not any(needle in item.lower() for item in haystacks):
            continue
        row: dict[str, Any] = {
            "parm_path": path,
            "name": name,
            "tuple": tuple_name,
            "type": _tuple_type_label(parm),
            "matches": matches,
        }
        if include_raw:
            row["raw"] = raw
        if include_expressions:
            row["expression"] = expression
            row["language"] = language
        if include_targets:
            row["resolved_targets"] = targets
        rows.append(row)
        if len(rows) >= max_matches:
            break
    return rows


def parm_refs_rows(
    session: Any,
    node: Any,
    *,
    external_to: str | None,
    recursive: bool,
    max_refs: int,
) -> list[dict[str, Any]]:
    rows = []
    nodes = [node]
    if recursive:
        try:
            nodes.extend(list(node.allSubChildren()))
        except Exception:
            pass
    for current in nodes:
        for parm in current.parms():
            if _parm_template_type(parm) in SKIPPED_TEMPLATE_TYPES:
                continue
            from_path = localize(parm.path())
            for target_path in target_paths(session, parm):
                row = {"from_parm": from_path, "to_parm": target_path}
                if external_to is not None:
                    row["external"] = not parm_within_root(target_path, external_to)
                rows.append(row)
                if len(rows) >= max_refs:
                    return rows
    return rows


def _get_node(session: Any, node_path: str) -> Any:
    node = session.hou.node(node_path)
    if node is None:
        raise ValueError(f"Node not found: {node_path}")
    return node


def parm_find_in_houdini(
    session: Any,
    node_path: str,
    *,
    query: str,
    include_raw: bool,
    include_expressions: bool,
    include_targets: bool,
    max_matches: int,
) -> list[dict[str, Any]]:
    if max_matches <= 0:
        raise ValueError(f"Maximum matches must be positive: {max_matches}")
    if not hasattr(session, "connection"):
        return parm_search_rows(
            session,
            _get_node(session, node_path),
            query=query,
            include_raw=include_raw,
            include_expressions=include_expressions,
            include_targets=include_targets,
            max_matches=max_matches,
        )
    session.connection.execute(REFERENCE_REMOTE_CODE)
    return localize(
        session.connection.eval(
            "_houdini_cli_parm_find("
            f"{node_path!r}, {query!r}, {bool(include_raw)!r}, "
            f"{bool(include_expressions)!r}, {bool(include_targets)!r}, {int(max_matches)!r})"
        )
    )


def parm_refs_in_houdini(
    session: Any,
    node_path: str,
    *,
    external_to: str | None,
    recursive: bool,
    max_refs: int,
) -> list[dict[str, Any]]:
    if max_refs <= 0:
        raise ValueError(f"Maximum refs must be positive: {max_refs}")
    if not hasattr(session, "connection"):
        return parm_refs_rows(
            session,
            _get_node(session, node_path),
            external_to=external_to,
            recursive=recursive,
            max_refs=max_refs,
        )
    session.connection.execute(REFERENCE_REMOTE_CODE)
    return localize(
        session.connection.eval(
            "_houdini_cli_parm_refs("
            f"{node_path!r}, {external_to!r}, {bool(recursive)!r}, {int(max_refs)!r})"
        )
    )


def _contained_nodes(node: Any) -> list[Any]:
    try:
        return [node, *list(node.allSubChildren())]
    except Exception:
        return [node]


def external_reference_rows(session: Any, asset_node: Any) -> dict[str, Any]:
    root_path = localize(asset_node.path())
    external: list[dict[str, Any]] = []
    absolute_internal: list[dict[str, Any]] = []
    all_refs: list[dict[str, Any]] = []

    for node in _contained_nodes(asset_node):
        for parm in node.parms():
            raw = safe_raw_value(parm)
            expression, language = safe_expression(parm)
            targets = resolved_channel_targets(
                session,
                parm,
                raw=raw,
                expression=expression,
                include_tuple_hom=True,
            )
            if not targets:
                continue
            from_parm = localize(parm.path())
            from_node = localize(node.path())
            for target in targets:
                target_path = str(target["target"])
                target_node = parm_node_path(target_path)
                external_ref = not within_node_root(target_node, root_path)
                absolute_internal_ref = (
                    not external_ref
                    and str(target.get("token", "")).startswith("/")
                    and within_node_root(target_node, root_path)
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


def external_references_in_houdini(session: Any, asset_node: Any) -> dict[str, Any]:
    if not hasattr(session, "connection"):
        return external_reference_rows(session, asset_node)
    asset_path = localize(asset_node.path())
    session.connection.execute(REFERENCE_REMOTE_CODE)
    return localize(
        session.connection.eval(f"_houdini_cli_hda_external_reference_audit({asset_path!r})")
    )


REFERENCE_REMOTE_CODE = r"""
import re
import hou

SKIPPED_TEMPLATE_TYPES = {"Button", "Folder", "FolderSet", "Label", "Separator"}
CHANNEL_REF_PATTERN = re.compile(r"\bch(?:s|f|i|v|p|raw)?\s*\(\s*['\"]([^'\"]+)['\"]")

def _houdini_cli_parm_tuple_type(parm):
    members = list(parm.tuple())
    template_type = parm.parmTemplate().type().name()
    return "{}{}".format(template_type, len(members)) if len(members) > 1 else template_type

def _houdini_cli_parm_raw(parm):
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

def _houdini_cli_parm_expression(parm):
    try:
        return parm.expression(), parm.expressionLanguage().name().lower()
    except Exception:
        return None, None

def _houdini_cli_parm_hom_targets(parm, include_tuple=False):
    paths = []
    owners = [parm, parm.tuple()] if include_tuple else [parm]
    for owner in owners:
        if not hasattr(owner, "references"):
            continue
        try:
            paths.extend(target.path() for target in owner.references())
        except Exception:
            pass
    return paths

def _houdini_cli_resolve_channel_ref(parm, token):
    if token.startswith("/"):
        target = hou.parm(token)
    elif "/" not in token:
        target = parm.node().parm(token)
    else:
        node_token, parm_name = token.rsplit("/", 1)
        target_node = parm.node().node(node_token)
        target = target_node.parm(parm_name) if target_node is not None else None
    return target.path() if target is not None else None

def _houdini_cli_channel_targets(parm, raw, expression, include_tuple_hom=False):
    seen = set()
    rows = []
    for path in _houdini_cli_parm_hom_targets(parm, include_tuple_hom):
        if path in seen:
            continue
        seen.add(path)
        rows.append({"target": path, "source": "hom", "token": path})
    for text in (expression, raw if isinstance(raw, str) else None):
        if not text:
            continue
        for match in CHANNEL_REF_PATTERN.finditer(text):
            token = match.group(1)
            target = _houdini_cli_resolve_channel_ref(parm, token)
            if target is None or target in seen:
                continue
            seen.add(target)
            rows.append({"target": target, "source": "expression", "token": token})
    return rows

def _houdini_cli_parm_targets(parm):
    raw = _houdini_cli_parm_raw(parm)
    expression, _language = _houdini_cli_parm_expression(parm)
    return [row["target"] for row in _houdini_cli_channel_targets(parm, raw, expression)]

def _houdini_cli_within_node_root(node_path, root_path):
    root = root_path.rstrip("/")
    return node_path == root or node_path.startswith(root + "/")

def _houdini_cli_parm_node_path(parm_path):
    return parm_path.rsplit("/", 1)[0]

def _houdini_cli_parm_find(node_path, query, include_raw, include_expressions, include_targets, max_matches):
    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)
    needle = query.lower()
    rows = []
    seen = set()
    for parm in node.parms():
        if parm.parmTemplate().type().name() in SKIPPED_TEMPLATE_TYPES:
            continue
        path = parm.path()
        if path in seen:
            continue
        seen.add(path)
        name = parm.name()
        tuple_name = parm.tuple().name()
        raw = _houdini_cli_parm_raw(parm)
        expression, language = _houdini_cli_parm_expression(parm)
        targets = _houdini_cli_parm_targets(parm)
        haystacks = [name, tuple_name, "" if raw is None else str(raw), expression or ""] + targets
        if not any(needle in item.lower() for item in haystacks):
            continue
        matches = []
        if any(needle in item.lower() for item in (name, tuple_name)):
            matches.append("name")
        if raw is not None and needle in str(raw).lower():
            matches.append("raw")
        if expression and needle in expression.lower():
            matches.append("expression")
        if any(needle in target.lower() for target in targets):
            matches.append("resolved_target")
        row = {
            "parm_path": path,
            "name": name,
            "tuple": tuple_name,
            "type": _houdini_cli_parm_tuple_type(parm),
            "matches": matches,
        }
        if include_raw:
            row["raw"] = raw
        if include_expressions:
            row["expression"] = expression
            row["language"] = language
        if include_targets:
            row["resolved_targets"] = targets
        rows.append(row)
        if len(rows) >= max_matches:
            break
    return rows

def _houdini_cli_parm_refs(node_path, external_to, recursive, max_refs):
    node = hou.node(node_path)
    if node is None:
        raise ValueError("Node not found: " + node_path)
    rows = []
    nodes = [node]
    if recursive:
        try:
            nodes.extend(list(node.allSubChildren()))
        except Exception:
            pass
    for current in nodes:
        for parm in current.parms():
            if parm.parmTemplate().type().name() in SKIPPED_TEMPLATE_TYPES:
                continue
            for target_path in _houdini_cli_parm_targets(parm):
                row = {"from_parm": parm.path(), "to_parm": target_path}
                if external_to is not None:
                    target_node = _houdini_cli_parm_node_path(target_path)
                    row["external"] = not _houdini_cli_within_node_root(target_node, external_to)
                rows.append(row)
                if len(rows) >= max_refs:
                    return rows
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
            raw = _houdini_cli_parm_raw(parm)
            expression, language = _houdini_cli_parm_expression(parm)
            targets = _houdini_cli_channel_targets(parm, raw, expression, True)
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
