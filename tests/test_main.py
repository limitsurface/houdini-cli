import json

from houdini_cli.main import build_parser, main


def test_build_parser_registers_new_command_groups() -> None:
    parser = build_parser()

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

    args = parser.parse_args(["opencl", "sync", "/obj/cops/opencl1", "--clear"])
    assert args.command == "opencl"
    assert args.opencl_command == "sync"
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

    args = parser.parse_args(["node", "parms", "find", "/obj/geo1", "--name", "dist"])
    assert args.command == "node"
    assert args.node_command == "parms"
    assert args.node_parms_command == "find"
    assert args.name == "dist"

    args = parser.parse_args(["node", "neighbors", "/obj/geo1/null1", "--depth", "2"])
    assert args.command == "node"
    assert args.node_command == "neighbors"
    assert args.depth == 2

    args = parser.parse_args(["session", "frame", "24"])
    assert args.command == "session"
    assert args.session_command == "frame"
    assert args.frame == 24

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
