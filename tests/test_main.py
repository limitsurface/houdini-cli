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
