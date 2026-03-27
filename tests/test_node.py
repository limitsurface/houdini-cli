from argparse import Namespace

import pytest

from houdini_cli.commands import node
from houdini_cli.commands import node_common


class FakeNodeTypeCategory:
    def name(self):
        return "Sop"


class FakeNodeType:
    def name(self):
        return "null"

    def category(self):
        return FakeNodeTypeCategory()


class FakeNode:
    def __init__(self, path="/obj/test", name="test") -> None:
        self._path = path
        self._name = name
        self.destroyed = False
        self.created = None

    def path(self):
        return self._path

    def name(self):
        return self._name

    def type(self):
        return FakeNodeType()

    def children(self):
        return []

    def inputs(self):
        return []

    def outputs(self):
        return []

    def isDisplayFlagSet(self):
        return False

    def isRenderFlagSet(self):
        return False

    def isBypassed(self):
        return False

    def createNode(self, node_type, name=None):
        self.created = FakeNode(f"{self._path}/{name or node_type}1", name or f"{node_type}1")
        return self.created

    def destroy(self):
        self.destroyed = True


class FakeSession:
    def __init__(self, nodes: dict[str, FakeNode]) -> None:
        self.hou = self
        self.nodes = nodes

    def node(self, path):
        return self.nodes.get(path)


class FakeConnect:
    def __init__(self, fake_session: FakeSession) -> None:
        self.fake_session = fake_session

    def __call__(self, host, port):
        class _Ctx:
            def __enter__(inner_self):
                return self.fake_session

            def __exit__(inner_self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_handle_get(monkeypatch) -> None:
    fake = FakeNode()
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({"/obj/test": fake})))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_get(
        Namespace(host="localhost", port=18811, node_path="/obj/test", section=None)
    )
    assert result["ok"] is True
    assert result["data"]["path"] == "/obj/test"
    assert result["data"]["type"] == "null"


def test_handle_create(monkeypatch) -> None:
    parent = FakeNode("/obj", "obj")
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({"/obj": parent})))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_create(
        Namespace(host="localhost", port=18811, parent_path="/obj", node_type="geo", name="demo")
    )
    assert result["ok"] is True
    assert result["data"]["path"] == "/obj/demo1"


def test_handle_delete(monkeypatch) -> None:
    fake = FakeNode()
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({"/obj/test": fake})))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_delete(Namespace(host="localhost", port=18811, node_path="/obj/test"))
    assert result["ok"] is True
    assert result["data"]["deleted"] is True
    assert fake.destroyed is True


def test_handle_get_section_parms(monkeypatch) -> None:
    fake = FakeNode()
    fake.parmsAsData = lambda brief=False: {"brief": brief, "parms": True}
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({"/obj/test": fake})))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_get(
        Namespace(host="localhost", port=18811, node_path="/obj/test", section="parms")
    )
    assert result["ok"] is True
    assert result["data"]["section"] == "parms"
    assert result["data"]["value"] == {"brief": False, "parms": True}


def test_handle_get_section_inputs(monkeypatch) -> None:
    fake = FakeNode()
    fake.inputsAsData = lambda: [{"from": "a", "to_index": 0}]
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({"/obj/test": fake})))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_get(
        Namespace(host="localhost", port=18811, node_path="/obj/test", section="inputs")
    )
    assert result["ok"] is True
    assert result["data"]["value"] == [{"from": "a", "to_index": 0}]


def test_handle_get_section_full(monkeypatch) -> None:
    fake = FakeNode()
    fake.asData = lambda **kwargs: {"full": True, "kwargs": kwargs}
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({"/obj/test": fake})))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_get(
        Namespace(host="localhost", port=18811, node_path="/obj/test", section="full")
    )
    assert result["ok"] is True
    assert result["data"]["section"] == "full"
    assert result["data"]["value"]["full"] is True


def test_handle_set_section_parms(monkeypatch) -> None:
    fake = FakeNode()
    called = {}
    fake.setParmsFromData = lambda payload: called.setdefault("payload", payload)
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({"/obj/test": fake})))
    monkeypatch.setattr(node, "load_json_input", lambda raw: {"parms": 1})

    result = node.handle_set(
        Namespace(host="localhost", port=18811, node_path="/obj/test", section="parms", json="{}")
    )
    assert result["ok"] is True
    assert called["payload"] == {"parms": 1}


def test_handle_set_section_inputs(monkeypatch) -> None:
    fake = FakeNode()
    called = {}
    fake.setInputsFromData = lambda payload: called.setdefault("payload", payload)
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({"/obj/test": fake})))
    monkeypatch.setattr(node, "load_json_input", lambda raw: [{"from": "a"}])

    result = node.handle_set(
        Namespace(host="localhost", port=18811, node_path="/obj/test", section="inputs", json="[]")
    )
    assert result["ok"] is True
    assert called["payload"] == [{"from": "a"}]


def test_handle_set_section_full(monkeypatch) -> None:
    fake = FakeNode()
    called = {}
    fake.setFromData = lambda payload: called.setdefault("payload", payload)
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({"/obj/test": fake})))
    monkeypatch.setattr(node, "load_json_input", lambda raw: {"full": 1})

    result = node.handle_set(
        Namespace(host="localhost", port=18811, node_path="/obj/test", section="full", json="{}")
    )
    assert result["ok"] is True
    assert called["payload"] == {"full": 1}


def test_missing_node_raises() -> None:
    with pytest.raises(ValueError, match="Node not found"):
        node_common.get_node(FakeSession({}), "/obj/missing")
