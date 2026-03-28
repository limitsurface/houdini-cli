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
