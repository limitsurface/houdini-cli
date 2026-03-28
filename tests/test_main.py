import json

from houdini_cli.main import main


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
