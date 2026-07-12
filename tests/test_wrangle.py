from argparse import Namespace

import pytest

from houdini_cli.commands import wrangle


class _Named:
    def __init__(self, value: str) -> None:
        self.value = value

    def name(self) -> str:
        return self.value


class _Type:
    def __init__(self, category: str, name: str) -> None:
        self._category = _Named(category)
        self._name = name

    def category(self) -> _Named:
        return self._category

    def name(self) -> str:
        return self._name


class _Node:
    def __init__(self, category: str, name: str, *, snippet: object | None = object()) -> None:
        self._type = _Type(category, name)
        self._snippet = snippet

    def type(self) -> _Type:
        return self._type

    def parm(self, name: str) -> object | None:
        return self._snippet if name == "snippet" else None

    def path(self) -> str:
        return "/test/wrangle"


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


@pytest.mark.parametrize("category,node_type", wrangle._SUPPORTED_WRANGLES)
def test_snippet_parm_supports_each_wrangle_kind(category: str, node_type: str) -> None:
    snippet = object()

    assert wrangle._snippet_parm(_Node(category, node_type, snippet=snippet)) is snippet


def test_snippet_parm_rejects_other_nodes_with_snippets() -> None:
    with pytest.raises(ValueError, match="not a supported VEX wrangle"):
        wrangle._snippet_parm(_Node("Sop", "other"))
