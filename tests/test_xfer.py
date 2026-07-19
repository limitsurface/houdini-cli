from argparse import Namespace
import os

import pytest

from houdini_cli.commands import xfer
from houdini_cli.main import build_parser
from houdini_cli.remote.xfer import XFER_REMOTE


def test_parser_registers_xfer_commands_and_capture_flags() -> None:
    parser = build_parser()
    export_args = parser.parse_args(
        [
            "--port", "18812", "xfer", "export", "/obj/geo1",
            "--output", "network.json", "--children", "--all-parms",
            "--editables", "--overwrite",
        ]
    )
    assert export_args.xfer_command == "export"
    assert export_args.port == 18812
    assert export_args.children is True
    assert export_args.all_parms is True
    assert export_args.editables is True
    assert export_args.overwrite is True

    copy_args = parser.parse_args(
        [
            "xfer", "copy", "/obj/source", "--to-parent", "/obj",
            "--from-port", "18812", "--to-port", "18811",
        ]
    )
    assert copy_args.xfer_command == "copy"
    assert copy_args.from_port == 18812
    assert copy_args.to_port == 18811


def test_remote_xfer_calls_only_pass_paths_and_scalar_options() -> None:
    assert XFER_REMOTE.call(
        "export", "/obj/geo1", "D:/tmp/network.json", True, False, False, False
    ) == "_houdini_cli_xfer_export('/obj/geo1', 'D:/tmp/network.json', True, False, False, False)"
    assert XFER_REMOTE.call(
        "import", "D:/tmp/network.json", "/obj", "copy", False
    ) == "_houdini_cli_xfer_import('D:/tmp/network.json', '/obj', 'copy', False)"


def test_export_rejects_stdout_artifact_path() -> None:
    with pytest.raises(ValueError, match="stdin or stdout"):
        xfer.handle_export(
            Namespace(
                host="localhost", port=18811, node_path="/obj/geo1", output="-",
                children=False, all_parms=False, editables=False, overwrite=False,
            )
        )


def test_export_localizes_status_before_connection_closes(monkeypatch) -> None:
    state = {"active": False}
    connection = object()

    class FakeConnect:
        def __enter__(self):
            state["active"] = True
            return Namespace(connection=connection)

        def __exit__(self, exc_type, exc, tb):
            state["active"] = False

    monkeypatch.setattr(xfer, "connect", lambda *args, **kwargs: FakeConnect())
    monkeypatch.setattr(
        xfer,
        "XFER_REMOTE",
        Namespace(evaluate=lambda *args: {"ok": True}),
    )

    def fake_remote_result(value, operation):
        assert state["active"] is True
        return {"status": operation}

    monkeypatch.setattr(xfer, "_remote_result", fake_remote_result)
    result = xfer._export_to(
        "localhost", 18811, "/obj/geo1", "D:/tmp/network.json",
        children=False, all_parms=False, editables=False, overwrite=False,
    )

    assert result == {"status": "export"}
    assert state["active"] is False


def test_copy_uses_temporary_artifact_and_returns_bounded_status(monkeypatch) -> None:
    observed = {}

    def fake_export(host, port, node_path, output_path, **options):
        observed["artifact"] = output_path
        assert (host, port, node_path) == ("localhost", 18812, "/obj/source")
        assert not os.path.exists(output_path)
        with open(output_path, "w", encoding="utf-8") as stream:
            stream.write("private payload")
        return {
            "path": output_path,
            "source": {"houdini_version": "22.0.368", "hip_file": "source.hipnc"},
            "capture": {"children": True, "all_parms": False, "editables": False, "evaluated": False},
            "summary": {"direct_nodes": 3, "direct_items": 5},
            "elapsed_seconds": 0.25,
        }

    def fake_import(host, port, artifact_path, parent_path, **options):
        assert (host, port) == ("localhost", 18811)
        assert artifact_path == observed["artifact"]
        assert os.path.exists(artifact_path)
        assert parent_path == "/obj"
        return {
            "path": "/obj/copied",
            "destination_houdini_version": "22.0.368",
            "destination_hip_file": "destination.hip",
            "destination_summary": {"direct_nodes": 3, "direct_items": 5},
            "verified": True,
            "error_count": 0,
            "warning_count": 0,
            "elapsed_seconds": 0.5,
        }

    monkeypatch.setattr(xfer, "_export_to", fake_export)
    monkeypatch.setattr(xfer, "_import_from", fake_import)
    result = xfer.handle_copy(
        Namespace(
            host="localhost", port=18811, node_path="/obj/source", to_parent="/obj",
            from_host=None, from_port=18812, to_host=None, to_port=18811,
            name=None, unique=False, children=True, all_parms=False, editables=False,
        )
    )

    assert result["ok"] is True
    assert result["data"]["verified"] is True
    assert result["data"]["source_summary"] == {"direct_nodes": 3, "direct_items": 5}
    assert not os.path.exists(observed["artifact"])
    assert "private payload" not in repr(result)


def test_copy_cleans_temporary_artifact_when_import_fails(monkeypatch) -> None:
    observed = {}

    def fake_export(host, port, node_path, output_path, **options):
        observed["artifact"] = output_path
        with open(output_path, "w", encoding="utf-8") as stream:
            stream.write("private payload")
        return {}

    def fake_import(*args, **kwargs):
        assert os.path.exists(observed["artifact"])
        raise RuntimeError("import failed")

    monkeypatch.setattr(xfer, "_export_to", fake_export)
    monkeypatch.setattr(xfer, "_import_from", fake_import)

    with pytest.raises(RuntimeError, match="import failed"):
        xfer.handle_copy(
            Namespace(
                host="localhost", port=18811, node_path="/obj/source", to_parent="/obj",
                from_host=None, from_port=18812, to_host=None, to_port=18811,
                name=None, unique=False, children=True, all_parms=False, editables=False,
            )
        )

    assert not os.path.exists(observed["artifact"])


def test_copy_rejects_different_hosts() -> None:
    with pytest.raises(ValueError, match="same host"):
        xfer.handle_copy(
            Namespace(
                host="localhost", port=18811, node_path="/obj/source", to_parent="/obj",
                from_host="source-host", from_port=18812,
                to_host="destination-host", to_port=18811,
                name=None, unique=False, children=False, all_parms=False, editables=False,
            )
        )
