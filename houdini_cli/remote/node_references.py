"""Remote node reference inspection entrypoint."""

from .module import RemoteModule

SOURCE = r"""
import hou

def _houdini_cli_node_reference_payload(root_path, external_only):
    root = hou.node(root_path)
    if root is None:
        raise ValueError("Node not found: " + root_path)

    def is_within_root(path):
        return path == root_path or path.startswith(root_path.rstrip("/") + "/")

    def connection_payload(connection):
        source = connection.inputNode()
        dest = connection.outputNode()
        return {
            "from_path": source.path() if source is not None else None,
            "from_output_index": int(connection.outputIndex()),
            "from_output_name": connection.inputName(),
            "from_output_label": connection.inputLabel(),
            "to_path": dest.path() if dest is not None else None,
            "to_input_index": int(connection.inputIndex()),
            "to_input_name": connection.outputName(),
            "to_input_label": connection.outputLabel(),
        }

    nodes = [root] + list(root.allSubChildren())
    parm_rows = []
    input_rows = []
    for node in nodes:
        for parameter in node.parms():
            try:
                targets = list(parameter.references())
            except Exception:
                continue
            for target in targets:
                target_path = target.path()
                target_node_path = target_path.rsplit("/", 1)[0]
                external = not is_within_root(target_node_path)
                if external_only and not external:
                    continue
                parm_rows.append(
                    {
                        "from_parm": parameter.path(),
                        "to_parm": target_path,
                        "external": external,
                    }
                )

        for connection in node.inputConnections():
            source = connection.inputNode()
            if source is None:
                continue
            source_path = source.path()
            external = not is_within_root(source_path)
            if external_only and not external:
                continue
            input_rows.append({**connection_payload(connection), "external": external})

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
"""

NODE_REFERENCE_REMOTE = RemoteModule(
    namespace="node_references",
    source=SOURCE,
    entrypoints={"payload": "_houdini_cli_node_reference_payload"},
)
