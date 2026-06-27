from argparse import Namespace

import pytest

from houdini_cli.commands import wrangle


def test_snippet_source_preserves_inline_vex() -> None:
    args = Namespace(vex="@P.y = 0;", input=None)

    assert wrangle._snippet_source(args) == "@P.y = 0;"


def test_snippet_source_reads_input_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wrangle, "read_text_input", lambda source: f"from {source}")
    args = Namespace(vex=None, input="-")

    assert wrangle._snippet_source(args) == "from -"


def test_snippet_source_reads_vex_dash_from_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wrangle, "read_text_input", lambda source: f"from {source}")
    args = Namespace(vex="-", input=None)

    assert wrangle._snippet_source(args) == "from -"
