"""Node parameter and input reference inspection."""

from __future__ import annotations

from typing import Any

from ..remote.node_references import NODE_REFERENCE_REMOTE
from ..transport.rpyc import localize
from .parm_refs import within_node_root


def _connection_payload(connection: Any) -> dict[str, Any]:
    source = connection.inputNode()
    dest = connection.outputNode()
    return {
        "from_path": localize(source.path()) if source is not None else None,
        "from_output_index": int(localize(connection.outputIndex())),
        "from_output_name": localize(connection.inputName()),
        "from_output_label": localize(connection.inputLabel()),
        "to_path": localize(dest.path()) if dest is not None else None,
        "to_input_index": int(localize(connection.inputIndex())),
        "to_input_name": localize(connection.outputName()),
        "to_input_label": localize(connection.outputLabel()),
    }


def _reference_payload(root: Any, *, external_only: bool) -> dict[str, Any]:
    root_path = localize(root.path())
    nodes = [root, *list(root.allSubChildren())]
    parm_rows = []
    input_rows = []

    for node in nodes:
        node_path = localize(node.path())
        for parameter in node.parms():
            try:
                targets = list(parameter.references())
            except Exception:
                continue
            for target in targets:
                target_path = localize(target.path())
                target_node_path = target_path.rsplit("/", 1)[0]
                external = not within_node_root(target_node_path, root_path)
                if external_only and not external:
                    continue
                parm_rows.append(
                    {
                        "from_parm": localize(parameter.path()),
                        "to_parm": target_path,
                        "external": external,
                    }
                )

        for connection in node.inputConnections():
            source = connection.inputNode()
            if source is None:
                continue
            source_path = localize(source.path())
            external = not within_node_root(source_path, root_path)
            if external_only and not external:
                continue
            input_rows.append({**_connection_payload(connection), "external": external})

    return {
        "node_path": root_path,
        "section": "references",
        "external_only": external_only,
        "parameter_references": parm_rows,
        "input_references": input_rows,
        "counts": {
            "parameter_references": len(parm_rows),
            "input_references": len(input_rows),
        },
    }


def reference_payload_in_houdini(
    session: Any,
    root_path: str,
    *,
    fallback_root: Any,
    external_only: bool,
) -> dict[str, Any]:
    connection = getattr(session, "connection", None)
    if not callable(getattr(connection, "execute", None)) or not callable(getattr(connection, "eval", None)):
        return _reference_payload(fallback_root, external_only=external_only)

    return localize(
        NODE_REFERENCE_REMOTE.evaluate(
            connection,
            "payload",
            root_path,
            bool(external_only),
        )
    )
