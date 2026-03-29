from argparse import Namespace

import pytest

from houdini_cli.commands import help as help_command


def test_handle_help_root() -> None:
    result = help_command.handle_help(Namespace(command_path=[]))

    assert result["ok"] is True
    assert result["data"]["commands"] == ["attrib", "cop", "eval", "node", "nodetype", "opencl", "parm", "ping", "session"]
    assert "stdout is JSON" in result["data"]["rules"]


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


def test_handle_help_session_frame_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["session", "frame"]))

    assert result["ok"] is True
    assert result["data"]["path"] == ["session", "frame"]
    assert result["data"]["usage"] == "houdini-cli session frame [<frame>]"


def test_handle_help_missing_topic_raises() -> None:
    with pytest.raises(ValueError, match="Help topic not found"):
        help_command.handle_help(Namespace(command_path=["missing"]))
