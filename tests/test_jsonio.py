import io
import sys

from houdini_cli.util.jsonio import load_json_input


def test_load_json_input_inline() -> None:
    assert load_json_input('{"x": 1}') == {"x": 1}


def test_load_json_input_stdin(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"x": 2}'))
    assert load_json_input("-") == {"x": 2}
