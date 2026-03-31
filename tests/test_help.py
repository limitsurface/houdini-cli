from argparse import Namespace

import pytest

from houdini_cli.commands import help as help_command


def test_handle_help_root() -> None:
    result = help_command.handle_help(Namespace(command_path=[]))

    assert result["ok"] is True
    assert result["data"]["commands"] == ["attrib", "cop", "eval", "node", "nodetype", "opencl", "parm", "ping", "session"]
    assert "opencl" in result["data"]["command_descriptions"]
    assert "OpenCL" in result["data"]["command_descriptions"]["opencl"]
    assert "stdout is JSON" in result["data"]["rules"]
    assert any(item["command"] == "houdini-cli opencl sync <node-path>" for item in result["data"]["workflows"])


def test_handle_help_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "nav"]))

    assert result["ok"] is True
    assert result["data"]["path"] == ["node", "nav"]
    assert "houdini-cli node nav" in result["data"]["usage"]
    assert "requires shared parent network" in result["data"]["notes"][0]


def test_handle_help_group_lists_subcommands() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm"]))

    assert result["ok"] is True
    assert result["data"]["subcommands"] == ["get", "menu", "set"]
    assert "OpenCL" in result["data"]["notes"][0]
    assert "set" in result["data"]["subcommand_descriptions"]


def test_handle_help_session_frame_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["session", "frame"]))

    assert result["ok"] is True
    assert result["data"]["path"] == ["session", "frame"]
    assert result["data"]["usage"] == "houdini-cli session frame [<frame>]"


def test_handle_help_opencl_topic_includes_discovery_context() -> None:
    result = help_command.handle_help(Namespace(command_path=["opencl"]))

    assert result["ok"] is True
    assert "Synchronize OpenCL node bindings" in result["data"]["description"]
    assert "sync" in result["data"]["subcommands"]
    assert "Refresh an OpenCL node" in result["data"]["subcommand_descriptions"]["sync"]
    assert "After editing an OpenCL kernel" in result["data"]["notes"][0]


def test_handle_help_opencl_sync_topic_has_examples() -> None:
    result = help_command.handle_help(Namespace(command_path=["opencl", "sync"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli opencl sync <node-path> [--clear] [--bindings-only]"
    assert any("--bindings-only" in example for example in result["data"]["examples"])


def test_handle_help_missing_topic_raises() -> None:
    with pytest.raises(ValueError, match="Help topic not found"):
        help_command.handle_help(Namespace(command_path=["missing"]))
