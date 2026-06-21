"""Remote parameter reference scanning entrypoints."""

from .module import RemoteModule

# The Houdini-side source is kept beside its registered entrypoints so callers
# never assemble function names or argument literals themselves.
SOURCE = r"""
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

PARM_REFERENCE_REMOTE = RemoteModule(
    namespace="parm_references",
    source=SOURCE,
    entrypoints={
        "find": "_houdini_cli_parm_find",
        "refs": "_houdini_cli_parm_refs",
        "hda_audit": "_houdini_cli_hda_external_reference_audit",
    },
)
