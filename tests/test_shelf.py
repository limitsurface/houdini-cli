from argparse import Namespace
from types import SimpleNamespace

import pytest

from houdini_cli.commands import shelf


class FakeTool:
    def __init__(self, name, label, script="", file_path="C:/test/default.shelf") -> None:
        self._name = name
        self._label = label
        self._script = script
        self._file_path = file_path
        self.destroyed = False

    def name(self):
        return self._name

    def label(self):
        return self._label

    def script(self):
        return self._script

    def setLabel(self, label):
        self._label = label

    def setScript(self, script):
        self._script = script

    def destroy(self):
        self.destroyed = True


class FakeShelf:
    def __init__(self, name, label, tools=None, file_path="C:/test/default.shelf") -> None:
        self._name = name
        self._label = label
        self._tools = list(tools or [])
        self._file_path = file_path

    def name(self):
        return self._name

    def label(self):
        return self._label

    def tools(self):
        return tuple(self._tools)

    def setTools(self, tools):
        self._tools = list(tools)

    def filePath(self):
        return self._file_path


class FakeShelves:
    def __init__(self, shelves, tools) -> None:
        self._shelves = shelves
        self._tools = tools
        self.change_depth = 0

    def shelves(self):
        return self._shelves

    def tools(self):
        return self._tools

    def tool(self, tool_name):
        return self._tools.get(tool_name)

    def newTool(self, **kwargs):
        tool = FakeTool(kwargs["name"], kwargs["label"], kwargs.get("script", ""), kwargs.get("file_path", ""))
        self._tools[kwargs["name"]] = tool
        return tool

    def beginChangeBlock(self):
        self.change_depth += 1

    def endChangeBlock(self):
        self.change_depth -= 1


class FakeSession:
    def __init__(self, fake_shelves) -> None:
        self.hou = SimpleNamespace(
            shelves=fake_shelves,
            scriptLanguage=SimpleNamespace(Python="Python"),
        )


class FakeConnect:
    def __init__(self, fake_session) -> None:
        self.fake_session = fake_session

    def __call__(self, host, port):
        class _Ctx:
            def __enter__(inner_self):
                return self.fake_session

            def __exit__(inner_self, exc_type, exc, tb):
                return False

        return _Ctx()


def _fixture():
    tool_a = FakeTool("houCLI", "houCLI")
    tool_b = FakeTool("print_selected_node_name_test", "printSelNode")
    pipe = FakeShelf("scy_Pipe", "Pipe", [tool_a, tool_b])
    other = FakeShelf("misc", "Misc", [])
    fake_shelves = FakeShelves({"scy_Pipe": pipe, "misc": other}, {"houCLI": tool_a, "print_selected_node_name_test": tool_b})
    return fake_shelves, pipe, other, tool_a, tool_b


def test_handle_list(monkeypatch) -> None:
    fake_shelves, *_ = _fixture()
    monkeypatch.setattr(shelf, "connect", FakeConnect(FakeSession(fake_shelves)))
    monkeypatch.setattr(shelf, "localize", lambda value: value)

    result = shelf.handle_list(Namespace(host="localhost", port=18811))
    assert result["data"]["cols"] == ["n", "l", "tc", "fp"]
    assert result["data"]["count"] == 2


def test_handle_tools(monkeypatch) -> None:
    fake_shelves, *_ = _fixture()
    monkeypatch.setattr(shelf, "connect", FakeConnect(FakeSession(fake_shelves)))
    monkeypatch.setattr(shelf, "localize", lambda value: value)

    result = shelf.handle_tools(Namespace(host="localhost", port=18811, shelf_name="scy_Pipe"))
    assert result["data"]["shelf"] == {"n": "scy_Pipe", "l": "Pipe"}
    assert result["data"]["rows"][-1] == ["print_selected_node_name_test", "printSelNode"]


def test_handle_find(monkeypatch) -> None:
    fake_shelves, *_ = _fixture()
    monkeypatch.setattr(shelf, "connect", FakeConnect(FakeSession(fake_shelves)))
    monkeypatch.setattr(shelf, "localize", lambda value: value)

    result = shelf.handle_find(Namespace(host="localhost", port=18811, query="print"))
    assert result["data"]["tools"]["rows"] == [["print_selected_node_name_test", "printSelNode", "scy_Pipe"]]


def test_handle_tool_add(monkeypatch) -> None:
    fake_shelves, pipe, _, _, _ = _fixture()
    monkeypatch.setattr(shelf, "connect", FakeConnect(FakeSession(fake_shelves)))
    monkeypatch.setattr(shelf, "localize", lambda value: value)
    monkeypatch.setattr(shelf, "_read_text_input", lambda _value: "print('hi')")

    result = shelf.handle_tool_add(
        Namespace(host="localhost", port=18811, shelf_name="scy_Pipe", tool_name="new_tool", label="New Tool", input="tool.py")
    )

    assert result["data"]["created"] is True
    assert pipe.tools()[-1].name() == "new_tool"


def test_handle_tool_edit(monkeypatch) -> None:
    fake_shelves, pipe, other, _, tool_b = _fixture()
    monkeypatch.setattr(shelf, "connect", FakeConnect(FakeSession(fake_shelves)))
    monkeypatch.setattr(shelf, "localize", lambda value: value)
    monkeypatch.setattr(shelf, "_read_text_input", lambda _value: "print('updated')")

    result = shelf.handle_tool_edit(
        Namespace(host="localhost", port=18811, tool_name="print_selected_node_name_test", label="Better", shelf_name="misc", input="tool.py")
    )

    assert result["data"]["updated"] is True
    assert tool_b.label() == "Better"
    assert tool_b.script() == "print('updated')"
    assert any(tool.name() == "print_selected_node_name_test" for tool in other.tools())
    assert "shelf" in result["data"]["applied"]


def test_handle_tool_delete_specific_shelf_destroys_orphan(monkeypatch) -> None:
    fake_shelves, pipe, _, _, tool_b = _fixture()
    monkeypatch.setattr(shelf, "connect", FakeConnect(FakeSession(fake_shelves)))
    monkeypatch.setattr(shelf, "localize", lambda value: value)

    result = shelf.handle_tool_delete(
        Namespace(host="localhost", port=18811, tool_name="print_selected_node_name_test", shelf_name="scy_Pipe")
    )

    assert result["data"]["deleted"] is True
    assert result["data"]["removed_from"] == ["scy_Pipe"]
    assert result["data"]["destroyed"] is True
    assert tool_b.destroyed is True
    assert all(tool.name() != "print_selected_node_name_test" for tool in pipe.tools())


def test_handle_tool_delete_all_shelves(monkeypatch) -> None:
    fake_shelves, pipe, other, _, tool_b = _fixture()
    other.setTools([tool_b])
    monkeypatch.setattr(shelf, "connect", FakeConnect(FakeSession(fake_shelves)))
    monkeypatch.setattr(shelf, "localize", lambda value: value)

    result = shelf.handle_tool_delete(
        Namespace(host="localhost", port=18811, tool_name="print_selected_node_name_test", shelf_name=None)
    )

    assert sorted(result["data"]["removed_from"]) == ["misc", "scy_Pipe"]
    assert result["data"]["destroyed"] is True


def test_handle_tool_add_rejects_existing(monkeypatch) -> None:
    fake_shelves, *_ = _fixture()
    monkeypatch.setattr(shelf, "connect", FakeConnect(FakeSession(fake_shelves)))
    monkeypatch.setattr(shelf, "localize", lambda value: value)
    monkeypatch.setattr(shelf, "_read_text_input", lambda _value: "print('hi')")

    with pytest.raises(ValueError, match="already exists"):
        shelf.handle_tool_add(
            Namespace(host="localhost", port=18811, shelf_name="scy_Pipe", tool_name="houCLI", label="Dup", input="tool.py")
        )
