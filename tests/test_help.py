import argparse
from argparse import Namespace

import pytest

from houdini_cli.commands import help as help_command
from houdini_cli.main import build_parser


def test_handle_help_root() -> None:
    result = help_command.handle_help(Namespace(command_path=[]))

    assert result["ok"] is True
    assert result["data"]["commands"] == ["attrib", "cop", "eval", "hda", "node", "nodetype", "opencl", "parm", "ping", "recipe", "session", "shelf", "wrangle"]
    assert "opencl" in result["data"]["command_descriptions"]
    assert "OpenCL" in result["data"]["command_descriptions"]["opencl"]
    assert "stdout is JSON" in result["data"]["rules"]
    assert result["data"]["legends"]["node_rows"]["cols"]["p"] == "path"
    assert result["data"]["legends"]["node_rows"]["flags"]["b"] == "bypass"
    assert result["data"]["legends"]["node_neighbors"]["nodes_cols"]["id"] == "response-local node id"
    assert result["data"]["legends"]["node_parm_rows"]["cols"]["v"] == "current value"
    assert any(item["command"] == "houdini-cli opencl sync <node-path>" for item in result["data"]["workflows"])


def test_top_level_help_topics_match_parser_commands() -> None:
    parser = build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert set(subparsers.choices) - {"help"} == set(help_command.HELP_TREE)


def test_handle_help_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "nav"]))

    assert result["ok"] is True
    assert result["data"]["path"] == ["node", "nav"]
    assert "houdini-cli node nav" in result["data"]["usage"]
    assert "requires shared parent network" in result["data"]["notes"][0]


def test_handle_help_group_lists_subcommands() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm"]))

    assert result["ok"] is True
    assert result["data"]["subcommands"] == [
        "default",
        "expression",
        "find",
        "full",
        "full-set",
        "get",
        "menu",
        "reference",
        "refs",
        "set",
        "template",
        "text-set",
        "tuple-set",
    ]
    assert "OpenCL" in result["data"]["notes"][0]
    assert "set" in result["data"]["subcommand_descriptions"]


def test_handle_help_node_group_lists_updated_subcommands() -> None:
    result = help_command.handle_help(Namespace(command_path=["node"]))

    assert result["ok"] is True
    assert "summary" not in result["data"]["subcommands"]
    assert "find" in result["data"]["subcommands"]
    assert "neighbors" in result["data"]["subcommands"]
    assert "parms" in result["data"]["subcommands"]
    assert "copy" in result["data"]["subcommands"]
    assert "move" in result["data"]["subcommands"]
    assert "rename" in result["data"]["subcommands"]
    assert "flags" in result["data"]["subcommands"]
    assert "compact row format" in result["data"]["subcommand_descriptions"]["find"]


def test_handle_help_parm_full_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm", "full"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli parm full <parm-path>"


def test_handle_help_parm_tuple_set_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm", "tuple-set"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli parm tuple-set <parm-path> <value> <value> ..."


def test_handle_help_parm_text_set_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm", "text-set"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli parm text-set <parm-path> --input <path-or-'-'>"


def test_handle_help_parm_full_set_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm", "full-set"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli parm full-set <parm-path> --input <path-or-'-'>"


def test_handle_help_parm_set_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm", "set"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli parm set <parm-path> <value>"


def test_handle_help_parm_template_set_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm", "template", "set"]))

    assert result["ok"] is True
    assert "--target instance|definition" in result["data"]["usage"]
    assert "named menu" in result["data"]["notes"][0]


def test_handle_help_parm_reference_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["parm", "reference"]))

    assert result["ok"] is True
    assert "chs()" in result["data"]["notes"][0]


def test_handle_help_node_set_mentions_batching() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "set"]))

    assert result["ok"] is True
    assert "--section parms" in result["data"]["notes"][0]


def test_handle_help_session_frame_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["session", "frame"]))

    assert result["ok"] is True
    assert result["data"]["path"] == ["session", "frame"]
    assert result["data"]["usage"] == "houdini-cli session frame [<frame>]"


def test_handle_help_session_save_as_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["session", "save-as"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli session save-as <path> [--force]"
    assert "existing destinations require --force" in result["data"]["notes"]


def test_handle_help_session_selection_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["session", "selection"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli session selection [--include-hidden]"
    assert "global current node" in result["data"]["notes"][0]


def test_handle_help_session_viewport_axis_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["session", "viewport", "axis"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli session viewport axis <+x|-x|+y|-y|+z|-z|persp> [--pane-name <name> | --index <n>]"


def test_handle_help_session_viewport_group_lists_subcommands() -> None:
    result = help_command.handle_help(Namespace(command_path=["session", "viewport"]))

    assert result["ok"] is True
    assert result["data"]["subcommands"] == ["axis", "focus-selected", "get", "set"]
    assert "free-camera state" in result["data"]["subcommand_descriptions"]["get"]


def test_handle_help_shelf_group_lists_subcommands() -> None:
    result = help_command.handle_help(Namespace(command_path=["shelf"]))

    assert result["ok"] is True
    assert result["data"]["subcommands"] == ["find", "list", "tool", "tools"]
    assert "compact row format" in result["data"]["subcommand_descriptions"]["list"]


def test_handle_help_shelf_tool_delete_topic() -> None:
    result = help_command.handle_help(Namespace(command_path=["shelf", "tool", "delete"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli shelf tool delete <tool-name> [--shelf <shelf-name>]"


def test_handle_help_node_list_topic_mentions_compact_schema() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "list"]))

    assert result["ok"] is True
    assert "compact row format" in result["data"]["description"]
    assert "legends.node_rows" in result["data"]["notes"][1]


def test_handle_help_node_neighbors_topic_mentions_legend() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "neighbors"]))

    assert result["ok"] is True
    assert "compact node and edge tables" in result["data"]["description"]
    assert "legends.node_neighbors" in result["data"]["notes"][0]


def test_handle_help_node_parms_list_topic_mentions_legend() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "parms", "list"]))

    assert result["ok"] is True
    assert "compact row format" in result["data"]["description"]
    assert "legends.node_parm_rows" in result["data"]["notes"][0]


def test_handle_help_node_set_topic_includes_input_examples() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "set"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli node set <node-path> --section parms|inputs|full --json <payload-or-'-'>"
    assert any("--section inputs" in note for note in result["data"]["notes"])
    assert any("from_index" in example and "to_index" in example for example in result["data"]["examples"])


def test_handle_help_node_move_clarifies_reparenting() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "move"]))

    assert result["ok"] is True
    assert "reparents nodes" in result["data"]["notes"][1]


def test_handle_help_node_flags_set_mentions_compress() -> None:
    result = help_command.handle_help(Namespace(command_path=["node", "flags", "set"]))

    assert result["ok"] is True
    assert "--compress BOOL" in result["data"]["usage"]


def test_handle_help_opencl_topic_includes_discovery_context() -> None:
    result = help_command.handle_help(Namespace(command_path=["opencl"]))

    assert result["ok"] is True
    assert "Synchronize OpenCL node bindings" in result["data"]["description"]
    assert "validate" in result["data"]["subcommands"]
    assert "sync" in result["data"]["subcommands"]
    assert "Refresh an OpenCL node" in result["data"]["subcommand_descriptions"]["sync"]
    assert "After editing an OpenCL kernel" in result["data"]["notes"][0]


def test_handle_help_opencl_sync_topic_has_examples() -> None:
    result = help_command.handle_help(Namespace(command_path=["opencl", "sync"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli opencl sync <node-path> [--clear] [--bindings-only] [--disconnect-invalid] [--no-preserve-spare-values] [--details]"
    assert any("--bindings-only" in example for example in result["data"]["examples"])


def test_handle_help_reference_audit_topics_include_new_flags() -> None:
    parm_refs = help_command.handle_help(Namespace(command_path=["parm", "refs"]))
    hda_validate = help_command.handle_help(Namespace(command_path=["hda", "validate"]))

    assert parm_refs["ok"] is True
    assert "--recursive" in parm_refs["data"]["usage"]
    assert hda_validate["ok"] is True
    assert "--external-references" in hda_validate["data"]["usage"]


def test_handle_help_opencl_validate_topic_has_usage() -> None:
    result = help_command.handle_help(Namespace(command_path=["opencl", "validate"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli opencl validate <node-path> [--details]"


def test_handle_help_cop_group_lists_info() -> None:
    result = help_command.handle_help(Namespace(command_path=["cop"]))

    assert result["ok"] is True
    assert "export-image" in result["data"]["subcommands"]
    assert "info" in result["data"]["subcommands"]
    assert "Sample" in result["data"]["subcommand_descriptions"]["sample"]


def test_handle_help_cop_info_topic_has_usage() -> None:
    result = help_command.handle_help(Namespace(command_path=["cop", "info"]))

    assert result["ok"] is True
    assert result["data"]["usage"] == "houdini-cli cop info <node-path> [--output <index-or-name>]"


def test_handle_help_cop_export_image_mentions_orientation() -> None:
    result = help_command.handle_help(Namespace(command_path=["cop", "export-image"]))

    assert result["ok"] is True
    assert "--mode raw|view" in result["data"]["usage"]
    assert any("map Y" in note for note in result["data"]["notes"])


def test_handle_help_missing_topic_raises() -> None:
    with pytest.raises(ValueError, match="Help topic not found"):
        help_command.handle_help(Namespace(command_path=["missing"]))


def test_handle_help_hda_group_lists_nested_groups() -> None:
    result = help_command.handle_help(Namespace(command_path=["hda"]))

    assert result["ok"] is True
    assert "inspect" in result["data"]["subcommands"]
    assert "parms" in result["data"]["subcommands"]
    assert "section" in result["data"]["subcommands"]
    assert "tool" in result["data"]["subcommands"]


def test_handle_help_hda_update_documents_order() -> None:
    result = help_command.handle_help(Namespace(command_path=["hda", "update"]))

    assert result["ok"] is True
    assert "contents -> interface" in result["data"]["notes"][0]
