import json

from houdini_cli.main import build_parser, main


def test_build_parser_registers_new_command_groups() -> None:
    parser = build_parser()

    args = parser.parse_args(["eval", "--input", "-"])
    assert args.code is None
    assert args.input == "-"

    args = parser.parse_args(["help", "node", "nav"])
    assert args.command == "help"
    assert args.command_path == ["node", "nav"]

    args = parser.parse_args(["nodetype", "get", "--category", "sop", "attribwrangle"])
    assert args.command == "nodetype"
    assert args.nodetype_command == "get"
    assert args.category == "sop"
    assert args.type_key == "attribwrangle"

    args = parser.parse_args(["attrib", "get", "/obj/geo1/OUT", "P", "--class", "point"])
    assert args.command == "attrib"
    assert args.attrib_command == "get"
    assert args.attrib_class == "point"

    args = parser.parse_args(["cop", "sample", "/obj/cops/constant1", "--x", "1", "--y", "2"])
    assert args.command == "cop"
    assert args.cop_command == "sample"
    assert args.x == 1
    assert args.y == 2

    args = parser.parse_args(["cop", "info", "/obj/cops/constant1"])
    assert args.command == "cop"
    assert args.cop_command == "info"
    assert args.output is None

    args = parser.parse_args(["opencl", "sync", "/obj/cops/opencl1", "--clear"])
    assert args.command == "opencl"
    assert args.opencl_command == "sync"
    assert args.clear is True
    assert args.disconnect_invalid is False

    args = parser.parse_args(["opencl", "validate", "/obj/cops/opencl1"])
    assert args.command == "opencl"
    assert args.opencl_command == "validate"

    args = parser.parse_args(
        [
            "wrangle",
            "create",
            "/obj/geo1",
            "--name",
            "grid",
            "--run-over",
            "detail",
            "--vex",
            'float scale = chf("scale");',
            "--create-spare-parms",
        ]
    )
    assert args.command == "wrangle"
    assert args.wrangle_command == "create"
    assert args.run_over == "detail"
    assert args.create_spare_parms is True

    args = parser.parse_args(["wrangle", "spare-parms", "sync", "/obj/geo1/grid", "--clear"])
    assert args.wrangle_spare_parms_command == "sync"
    assert args.clear is True

    args = parser.parse_args(["parm", "full", "/obj/geo1/box1/sizex"])
    assert args.command == "parm"
    assert args.parm_command == "full"

    args = parser.parse_args(["parm", "set", "/obj/geo1/box1/sizex", "2.5"])
    assert args.command == "parm"
    assert args.parm_command == "set"
    assert args.value == "2.5"

    args = parser.parse_args(["parm", "tuple-set", "/obj/geo1/xform1/t", "1", "2", "3"])
    assert args.command == "parm"
    assert args.parm_command == "tuple-set"
    assert args.values == ["1", "2", "3"]

    args = parser.parse_args(["parm", "text-set", "/obj/geo1/wrangle1/snippet", "--input", "-"])
    assert args.command == "parm"
    assert args.parm_command == "text-set"
    assert args.input == "-"

    args = parser.parse_args(["parm", "full-set", "/obj/geo1/copytopoints1/targetattribs", "--input", "payload.json"])
    assert args.command == "parm"
    assert args.parm_command == "full-set"
    assert args.input == "payload.json"

    args = parser.parse_args(["parm", "expression", "set", "/obj/x/size", "--input", "-"])
    assert args.parm_command == "expression"
    assert args.parm_expression_command == "set"
    assert args.input == "-"

    args = parser.parse_args(["parm", "reference", "/obj/x/a", "/obj/x/b", "--absolute"])
    assert args.parm_command == "reference"
    assert args.absolute is True

    args = parser.parse_args(["parm", "template", "set", "/obj/x/size", "--target", "definition", "--input", "-"])
    assert args.parm_template_command == "set"
    assert args.target == "definition"

    args = parser.parse_args(["parm", "default", "set", "/obj/x/size", "--current"])
    assert args.parm_default_command == "set"
    assert args.current is True

    args = parser.parse_args(["shelf", "find", "--query", "pipe"])
    assert args.command == "shelf"
    assert args.shelf_command == "find"
    assert args.query == "pipe"

    args = parser.parse_args(["shelf", "tool", "delete", "print_selected_node_name_test", "--shelf", "scy_Pipe"])
    assert args.command == "shelf"
    assert args.shelf_command == "tool"
    assert args.shelf_tool_command == "delete"
    assert args.shelf_name == "scy_Pipe"

    args = parser.parse_args(["node", "parms", "find", "/obj/geo1", "--name", "dist"])
    assert args.command == "node"
    assert args.node_command == "parms"
    assert args.node_parms_command == "find"
    assert args.name == "dist"

    args = parser.parse_args(["node", "neighbors", "/obj/geo1/null1", "--depth", "2"])
    assert args.command == "node"
    assert args.node_command == "neighbors"
    assert args.depth == 2

    args = parser.parse_args(["node", "rename", "/obj/geo1/old", "new", "--unique"])
    assert args.node_command == "rename"
    assert args.unique is True

    args = parser.parse_args(["node", "copy", "/obj/geo1/a", "/obj/geo1/b", "--parent", "/obj/geo2"])
    assert args.node_command == "copy"
    assert args.node_paths == ["/obj/geo1/a", "/obj/geo1/b"]

    args = parser.parse_args(["node", "move", "/obj/geo1/a", "--parent", "/obj/geo2"])
    assert args.node_command == "move"

    args = parser.parse_args(["node", "get", "/obj/geo1", "--section", "references", "--external-only"])
    assert args.section == "references"
    assert args.external_only is True

    args = parser.parse_args(["node", "flags", "set", "/obj/geo1/a", "--compress", "false"])
    assert args.node_command == "flags"
    assert args.node_flags_command == "set"
    assert args.compress is False

    args = parser.parse_args(["hda", "inspect", "/obj/geo1/asset1", "--parms"])
    assert args.command == "hda"
    assert args.hda_command == "inspect"
    assert args.parms is True

    args = parser.parse_args(
        [
            "hda",
            "create",
            "/obj/geo1/subnet1",
            "--type-name",
            "Scy::test::1.0",
            "--label",
            "Test",
            "--library",
            "test.hda",
        ]
    )
    assert args.hda_command == "create"
    assert args.on_existing == "error"

    args = parser.parse_args(["hda", "section", "set", "/obj/geo1/asset1", "Help", "--input", "-"])
    assert args.hda_section_command == "set"

    args = parser.parse_args(["hda", "update", "/obj/geo1/asset1", "--all"])
    assert args.all is True

    args = parser.parse_args(["session", "frame", "24"])
    assert args.command == "session"
    assert args.session_command == "frame"
    assert args.frame == 24

    args = parser.parse_args(["session", "save"])
    assert args.session_command == "save"

    args = parser.parse_args(["session", "save-as", "D:/shots/test.hip", "--force"])
    assert args.session_command == "save-as"
    assert args.path == "D:/shots/test.hip"
    assert args.force is True

    args = parser.parse_args(["session", "selection", "--include-hidden"])
    assert args.command == "session"
    assert args.session_command == "selection"
    assert args.include_hidden is True

    args = parser.parse_args(["session", "viewport", "axis", "+x"])
    assert args.command == "session"
    assert args.session_command == "viewport"
    assert args.viewport_command == "axis"
    assert args.axis == "+x"

    args = parser.parse_args(["session", "viewport", "set", "--t", "1", "2", "3", "--r", "10", "20", "30"])
    assert args.command == "session"
    assert args.session_command == "viewport"
    assert args.viewport_command == "set"
    assert args.t == [1.0, 2.0, 3.0]
    assert args.r == [10.0, 20.0, 30.0]


def test_main_returns_zero_for_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "houdini_cli.commands.session.handle_ping",
        lambda _args: {"ok": True, "data": {"pong": True}},
    )

    exit_code = main(["ping"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == {"ok": True, "data": {"pong": True}}


def test_main_outputs_error_json_for_unknown_runtime_failure(monkeypatch, capsys) -> None:
    def broken(_args):
        raise RuntimeError("boom")

    monkeypatch.setattr("houdini_cli.commands.session.handle_ping", broken)
    exit_code = main(["ping"])
    captured = capsys.readouterr()

    assert exit_code == 1
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["error"]["message"] == "boom"


def test_main_default_error_logging_is_concise(monkeypatch, capsys) -> None:
    def broken(_args):
        raise RuntimeError("boom")

    monkeypatch.setattr("houdini_cli.commands.session.handle_ping", broken)
    exit_code = main(["ping"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Traceback" not in captured.err
    assert "CLI command failed: boom" in captured.err


def test_main_debug_error_logging_includes_traceback(monkeypatch, capsys) -> None:
    def broken(_args):
        raise RuntimeError("boom")

    monkeypatch.setattr("houdini_cli.commands.session.handle_ping", broken)
    exit_code = main(["--debug", "ping"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Traceback" in captured.err
