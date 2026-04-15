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
    assert result["data"]["legends"]["node_rows"]["cols"]["p"] == "path"
    assert result["data"]["legends"]["node_rows"]["flags"]["b"] == "bypass"
    assert result["data"]["legends"]["node_inspect"]["keys"]["parms"] == "non-default parameter names"
    assert result["data"]["legends"]["node_parm_rows"]["cols"]["v"] == "current value"
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
    assert result["data"]["subcommands"] == ["full", "get", "menu", "set"]
    assert "OpenCL" in result["data"]["notes"][0]
    assert "set" in result["data"]["subcommand_descriptions"]


def test_handle_help_node_group_lists_updated_subcommands() -> None:
    result = help_command.handle_help(Namespace(command_path=["node"]))

    assert result["ok"] is True
    assert "summary" not in result["data"]["subcommands"]
    assert "find" in result["data"]["subcommands"]
    assert "parms" in result["data"]["subcommands"]
    assert "compact row format" in result["data"]["subcommand_descriptions"]["find"]


def test_handle_help_parm_full_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm", "full"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli parm full <parm-path>"


def test_handle_help_parm_set_mentions_batched_node_edits() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm", "set"]))

    assert result["ok"] is True
    assert "node set" in result["data"]["notes"][0]


def test_handle_help_node_set_mentions_batching() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "set"]))

    assert result["ok"] is True
    assert "--section parms" in result["data"]["notes"][0]


def test_handle_help_session_frame_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["session", "frame"]))

    assert result["ok"] is True
    assert result["data"]["path"] == ["session", "frame"]
    assert result["data"]["usage"] == "houdini-cli session frame [<frame>]"


def test_handle_help_node_list_topic_mentions_compact_schema() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "list"]))

    assert result["ok"] is True
    assert "compact row format" in result["data"]["description"]
    assert "legends.node_rows" in result["data"]["notes"][1]


def test_handle_help_node_inspect_topic_mentions_legend() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "inspect"]))

    assert result["ok"] is True
    assert "compact object format" in result["data"]["description"]
    assert "legends.node_inspect" in result["data"]["notes"][0]


def test_handle_help_node_parms_list_topic_mentions_legend() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "parms", "list"]))

    assert result["ok"] is True
    assert "compact row format" in result["data"]["description"]
    assert "legends.node_parm_rows" in result["data"]["notes"][0]


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
