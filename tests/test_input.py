import io

import pytest

from houdini_cli.util.input import read_json_input, read_text_input


def test_read_text_input_from_stdin() -> None:
    assert read_text_input("-", stdin=io.StringIO("hello\n")) == "hello\n"


def test_read_text_input_from_utf8_file(tmp_path) -> None:
    path = tmp_path / "script.py"
    path.write_text("print('hello')\n", encoding="utf-8")

    assert read_text_input(str(path)) == "print('hello')\n"


def test_read_text_input_rejects_empty_stdin() -> None:
    with pytest.raises(ValueError, match="Input from stdin is empty"):
        read_text_input("-", stdin=io.StringIO(""))


def test_read_json_input_reports_source_and_position() -> None:
    with pytest.raises(ValueError, match=r"stdin at line 1, column 7"):
        read_json_input("-", stdin=io.StringIO('{"x": }'))


def test_read_json_input_from_file(tmp_path) -> None:
    path = tmp_path / "payload.json"
    path.write_text('{"x": 2}', encoding="utf-8")

    assert read_json_input(str(path)) == {"x": 2}
