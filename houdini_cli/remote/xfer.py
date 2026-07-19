"""Houdini-side filesystem transport for node data artifacts."""

from __future__ import annotations

from .module import RemoteModule


XFER_REMOTE_SOURCE = r'''
def _houdini_cli_xfer_bounded_error(exc):
    text = str(exc).strip() or exc.__class__.__name__
    return text if len(text) <= 500 else text[:497] + "..."


def _houdini_cli_xfer_record_count(value):
    if isinstance(value, dict):
        count = 1 if "type" in value else 0
        return count + sum(_houdini_cli_xfer_record_count(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_houdini_cli_xfer_record_count(item) for item in value)
    return 0


def _houdini_cli_xfer_expand_path(path):
    import os
    import hou

    return os.path.abspath(hou.expandString(path))


def _houdini_cli_xfer_export(node_path, output_path, children, all_parms, editables, overwrite):
    import json
    import os
    import tempfile
    import time
    import hou

    started = time.perf_counter()
    node = hou.node(node_path)
    if node is None:
        return {"ok": False, "error": "Node not found: " + node_path}

    resolved_output = _houdini_cli_xfer_expand_path(output_path)
    if os.path.exists(resolved_output) and not overwrite:
        return {"ok": False, "error": "Output file already exists: " + resolved_output}

    output_directory = os.path.dirname(resolved_output)
    if not output_directory:
        return {"ok": False, "error": "Output path has no parent directory: " + resolved_output}
    os.makedirs(output_directory, exist_ok=True)

    temporary_path = None
    try:
        data = node.asData(
            children=bool(children),
            editables=bool(editables),
            inputs=True,
            position=True,
            flags=True,
            parms=True,
            default_parmvalues=bool(all_parms),
            evaluate_parmvalues=False,
            parms_as_brief=True,
            parmtemplates="spare_only",
            metadata=False,
        )
        child_data = data.get("children", {}) if isinstance(data, dict) else {}
        summary = {
            "direct_nodes": len(node.children()) if children else 0,
            "direct_items": len(node.allItems()) if children else 0,
            "captured_records": _houdini_cli_xfer_record_count(data),
            "captured_items": len(child_data) if isinstance(child_data, dict) else 0,
        }
        envelope = {
            "schema": "houdini-cli.xfer",
            "schema_version": 1,
            "source": {
                "houdini_version": hou.applicationVersionString(),
                "hip_file": hou.hipFile.path(),
                "node_path": node.path(),
                "node_name": node.name(),
                "node_type": node.type().name(),
            },
            "capture": {
                "children": bool(children),
                "all_parms": bool(all_parms),
                "editables": bool(editables),
                "evaluated": False,
            },
            "summary": summary,
            "data": data,
        }

        descriptor, temporary_path = tempfile.mkstemp(
            prefix="." + os.path.basename(resolved_output) + ".",
            suffix=".tmp",
            dir=output_directory,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(envelope, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())

        if os.path.exists(resolved_output) and not overwrite:
            raise FileExistsError("Output file already exists: " + resolved_output)
        os.replace(temporary_path, resolved_output)
        temporary_path = None
        return {
            "ok": True,
            "path": resolved_output,
            "bytes": os.path.getsize(resolved_output),
            "source": envelope["source"],
            "capture": envelope["capture"],
            "summary": summary,
            "elapsed_seconds": time.perf_counter() - started,
        }
    except Exception as exc:
        return {"ok": False, "error": _houdini_cli_xfer_bounded_error(exc)}
    finally:
        if temporary_path and os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass


def _houdini_cli_xfer_import(input_path, parent_path, name, unique):
    import json
    import os
    import time
    import hou

    started = time.perf_counter()
    resolved_input = _houdini_cli_xfer_expand_path(input_path)
    if not os.path.isfile(resolved_input):
        return {"ok": False, "error": "Artifact file not found: " + resolved_input}

    parent = hou.node(parent_path)
    if parent is None:
        return {"ok": False, "error": "Destination parent not found: " + parent_path}
    if not parent.isEditable():
        return {"ok": False, "error": "Destination parent is not editable: " + parent.path()}

    created = None
    previous_update_mode = hou.updateModeSetting()
    try:
        with open(resolved_input, "r", encoding="utf-8") as stream:
            envelope = json.load(stream)
        if not isinstance(envelope, dict):
            raise ValueError("Artifact root must be a JSON object")
        if envelope.get("schema") != "houdini-cli.xfer":
            raise ValueError("Unsupported artifact schema")
        if envelope.get("schema_version") != 1:
            raise ValueError("Unsupported artifact schema version")

        source = envelope.get("source")
        capture = envelope.get("capture")
        source_summary = envelope.get("summary")
        data = envelope.get("data")
        if not isinstance(source, dict) or not isinstance(capture, dict):
            raise ValueError("Artifact source and capture metadata are required")
        if not isinstance(source_summary, dict) or not isinstance(data, dict):
            raise ValueError("Artifact summary and node data are required")

        root_type = source.get("node_type")
        source_name = source.get("node_name")
        if not isinstance(root_type, str) or not root_type:
            raise ValueError("Artifact source node type is missing")
        destination_name = name if name is not None else source_name
        if not isinstance(destination_name, str) or not destination_name:
            raise ValueError("Destination node name is missing")
        if parent.node(destination_name) is not None and not unique:
            raise ValueError("Destination node already exists: " + parent.path() + "/" + destination_name)

        hou.setUpdateMode(hou.updateMode.Manual)
        created = parent.createNode(root_type, destination_name)
        if hasattr(created, "setDisplayFlag"):
            try:
                created.setDisplayFlag(False)
            except Exception:
                pass
        created.setFromData(
            data,
            clear_content=True,
            force_item_creation=True,
            parms=True,
            parmtemplates=True,
            children=True,
            editables=True,
            skip_notes=False,
        )

        destination_summary = {
            "direct_nodes": len(created.children()),
            "direct_items": len(created.allItems()),
        }
        source_nodes = int(source_summary.get("direct_nodes", 0))
        source_items = int(source_summary.get("direct_items", 0))
        children_captured = bool(capture.get("children", False))
        verified = (
            created.type().name() == root_type
            and (not children_captured or destination_summary["direct_nodes"] == source_nodes)
            and (not children_captured or destination_summary["direct_items"] == source_items)
        )

        inspected = [created]
        if children_captured:
            inspected.extend(created.children())
        error_count = 0
        warning_count = 0
        for inspected_node in inspected:
            try:
                error_count += len(inspected_node.errors())
                warning_count += len(inspected_node.warnings())
            except Exception:
                pass

        return {
            "ok": True,
            "path": created.path(),
            "name": created.name(),
            "type": created.type().name(),
            "destination_houdini_version": hou.applicationVersionString(),
            "destination_hip_file": hou.hipFile.path(),
            "source": source,
            "capture": capture,
            "source_summary": source_summary,
            "destination_summary": destination_summary,
            "error_count": error_count,
            "warning_count": warning_count,
            "verified": verified,
            "elapsed_seconds": time.perf_counter() - started,
        }
    except Exception as exc:
        partial_path = None
        if created is not None:
            try:
                partial_path = created.path()
                created.destroy()
            except Exception:
                pass
        result = {"ok": False, "error": _houdini_cli_xfer_bounded_error(exc)}
        if partial_path:
            result["removed_partial_path"] = partial_path
        return result
    finally:
        hou.setUpdateMode(previous_update_mode)
'''


XFER_REMOTE = RemoteModule(
    namespace="xfer",
    source=XFER_REMOTE_SOURCE,
    entrypoints={
        "export": "_houdini_cli_xfer_export",
        "import": "_houdini_cli_xfer_import",
    },
)
