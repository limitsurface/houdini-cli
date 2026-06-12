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
        self.parent_node = None
        self.selected_calls = []
        self.renamed = None
        self.display = False
        self.render = False
        self.bypassed = False
        self.compressed = False
        self._children = []
        self._parms = []
        self._input_connections = []

    def path(self):
        return self._path

    def name(self):
        return self._name

    def parent(self):
        return self.parent_node

    def type(self):
        return FakeNodeType()

    def children(self):
        return self._children

    def childTypeCategory(self):
        return FakeNodeTypeCategory()

    def allSubChildren(self):
        return self._children

    def parms(self):
        return self._parms

    def inputConnections(self):
        return self._input_connections

    def inputs(self):
        return []

    def outputs(self):
        return []

    def isDisplayFlagSet(self):
        return self.display

    def isRenderFlagSet(self):
        return self.render

    def isBypassed(self):
        return self.bypassed

    def createNode(self, node_type, name=None):
        self.created = FakeNode(f"{self._path}/{name or node_type}1", name or f"{node_type}1")
        return self.created

    def destroy(self):
        self.destroyed = True

    def setName(self, name, unique_name=False):
        self.renamed = (name, unique_name)
        self._name = f"{name}1" if unique_name else name
        parent_path = self._path.rsplit("/", 1)[0]
        self._path = f"{parent_path}/{self._name}"

    def setDisplayFlag(self, value):
        self.display = value

    def setRenderFlag(self, value):
        self.render = value

    def bypass(self, value):
        self.bypassed = value

    def isGenericFlagSet(self, _flag):
        return self.compressed

    def setGenericFlag(self, _flag, value):
        self.compressed = value

    def setSelected(self, selected, clear_all_selected=False):
        self.selected_calls.append((selected, clear_all_selected))


class FakeNetworkEditor:
    def __init__(self) -> None:
        self.pwd_node = None
        self.current_node = None
        self.framed = False
        self.cleared = False

    def setPwd(self, node):
        self.pwd_node = node

    def setCurrentNode(self, node):
        self.current_node = node

    def frameSelection(self):
        self.framed = True

    def clearAllSelected(self):
        self.cleared = True


class FakeParm:
    def __init__(self, path, references=None):
        self._path = path
        self._references = references or []

    def path(self):
        return self._path

    def references(self):
        return self._references


class FakeSession:
    def __init__(self, nodes: dict[str, FakeNode], pane_tabs=None) -> None:
        self.hou = self
        self.nodes = nodes
        self._pane_tabs = pane_tabs or []
        self.ui = self
        self.nodeFlag = type("NodeFlag", (), {"Compress": object()})
        self.data = type("Data", (), {})()

    def node(self, path):
        return self.nodes.get(path)

    def isUIAvailable(self):
        return True

    def paneTabs(self):
        return self._pane_tabs

    def dataNodeTypeCategory(self):
        return type("DataCategory", (), {"nodeTypes": lambda self: {}})()

    def moveNodesTo(self, nodes, destination):
        return destination.moved_nodes


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


def test_handle_rename(monkeypatch) -> None:
    fake = FakeNode("/obj/geo1/old", "old")
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({fake.path(): fake})))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_rename(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/geo1/old",
            new_name="renamed",
            unique=False,
        )
    )

    assert result["data"]["old_path"] == "/obj/geo1/old"
    assert result["data"]["new_path"] == "/obj/geo1/renamed"
    assert fake.renamed == ("renamed", False)


def test_handle_copy_returns_path_map(monkeypatch) -> None:
    source_parent = FakeNode("/obj/source", "source")
    destination = FakeNode("/obj/destination", "destination")
    first = FakeNode("/obj/source/a", "a")
    second = FakeNode("/obj/source/b", "b")
    first.parent_node = source_parent
    second.parent_node = source_parent
    copied = [FakeNode("/obj/destination/a", "a"), FakeNode("/obj/destination/b", "b")]
    destination.copyItems = lambda items, **kwargs: copied
    session = FakeSession(
        {
            source_parent.path(): source_parent,
            destination.path(): destination,
            first.path(): first,
            second.path(): second,
        }
    )
    monkeypatch.setattr(node, "connect", FakeConnect(session))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_copy(
        Namespace(
            host="localhost",
            port=18811,
            node_paths=[first.path(), second.path()],
            parent=destination.path(),
        )
    )

    assert result["data"]["path_map"] == {
        "/obj/source/a": "/obj/destination/a",
        "/obj/source/b": "/obj/destination/b",
    }


def test_handle_move_returns_path_map(monkeypatch) -> None:
    source_parent = FakeNode("/obj/source", "source")
    destination = FakeNode("/obj/destination", "destination")
    first = FakeNode("/obj/source/a", "a")
    first.parent_node = source_parent
    moved = [FakeNode("/obj/destination/a", "a")]
    destination.moved_nodes = moved
    session = FakeSession(
        {
            source_parent.path(): source_parent,
            destination.path(): destination,
            first.path(): first,
        }
    )
    monkeypatch.setattr(node, "connect", FakeConnect(session))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_move(
        Namespace(
            host="localhost",
            port=18811,
            node_paths=[first.path()],
            parent=destination.path(),
        )
    )

    assert result["data"]["path_map"] == {"/obj/source/a": "/obj/destination/a"}


def test_handle_flags_set(monkeypatch) -> None:
    fake = FakeNode()
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({fake.path(): fake})))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_flags_set(
        Namespace(
            host="localhost",
            port=18811,
            node_path=fake.path(),
            display=True,
            render=False,
            bypass=True,
            compress=False,
        )
    )

    assert result["data"]["flags"] == {
        "display": True,
        "render": False,
        "bypass": True,
        "compress": False,
    }


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


def test_handle_get_section_references_external_only(monkeypatch) -> None:
    root = FakeNode("/obj/geo1/subnet1", "subnet1")
    child = FakeNode("/obj/geo1/subnet1/child", "child")
    internal = FakeParm("/obj/geo1/subnet1/other/value")
    external = FakeParm("/obj/geo1/config/value")
    child._parms = [
        FakeParm("/obj/geo1/subnet1/child/internal", [internal]),
        FakeParm("/obj/geo1/subnet1/child/external", [external]),
    ]
    root._children = [child]
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession({root.path(): root})))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_get(
        Namespace(
            host="localhost",
            port=18811,
            node_path=root.path(),
            section="references",
            external_only=True,
        )
    )

    assert result["data"]["counts"]["parameter_references"] == 1
    assert result["data"]["parameter_references"][0]["to_parm"] == "/obj/geo1/config/value"
    assert result["data"]["parameter_references"][0]["external"] is True


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


def test_handle_nav(monkeypatch) -> None:
    network = FakeNode("/obj/geo1", "geo1")
    box = FakeNode("/obj/geo1/box1", "box1")
    null = FakeNode("/obj/geo1/null1", "null1")
    box.parent_node = network
    null.parent_node = network
    editor = FakeNetworkEditor()

    monkeypatch.setattr(
        node,
        "connect",
        FakeConnect(
            FakeSession(
                {
                    "/obj/geo1": network,
                    "/obj/geo1/box1": box,
                    "/obj/geo1/null1": null,
                },
                pane_tabs=[editor],
            )
        ),
    )
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_nav(
        Namespace(
            host="localhost",
            port=18811,
            node_paths=["/obj/geo1/box1", "/obj/geo1/null1"],
            no_frame=False,
            no_select=False,
            no_current=False,
        )
    )

    assert result["ok"] is True
    assert result["data"]["network"] == "/obj/geo1"
    assert result["data"]["current"] == "/obj/geo1/null1"
    assert editor.pwd_node is network
    assert editor.current_node is null
    assert editor.framed is True
    assert box.selected_calls == [(True, True)]
    assert null.selected_calls == [(True, False)]


def test_handle_nav_requires_same_parent(monkeypatch) -> None:
    network_a = FakeNode("/obj/geo1", "geo1")
    network_b = FakeNode("/obj/geo2", "geo2")
    box = FakeNode("/obj/geo1/box1", "box1")
    null = FakeNode("/obj/geo2/null1", "null1")
    box.parent_node = network_a
    null.parent_node = network_b
    editor = FakeNetworkEditor()

    monkeypatch.setattr(
        node,
        "connect",
        FakeConnect(
            FakeSession(
                {
                    "/obj/geo1/box1": box,
                    "/obj/geo2/null1": null,
                },
                pane_tabs=[editor],
            )
        ),
    )
    monkeypatch.setattr(node, "localize", lambda value: value)

    with pytest.raises(ValueError, match="same parent"):
        node.handle_nav(
            Namespace(
                host="localhost",
                port=18811,
                node_paths=["/obj/geo1/box1", "/obj/geo2/null1"],
                no_frame=False,
                no_select=False,
                no_current=False,
            )
        )


def test_handle_nav_without_selection_clears_after_frame(monkeypatch) -> None:
    network = FakeNode("/obj/geo1", "geo1")
    box = FakeNode("/obj/geo1/box1", "box1")
    box.parent_node = network
    editor = FakeNetworkEditor()

    monkeypatch.setattr(
        node,
        "connect",
        FakeConnect(
            FakeSession(
                {
                    "/obj/geo1": network,
                    "/obj/geo1/box1": box,
                },
                pane_tabs=[editor],
            )
        ),
    )
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_nav(
        Namespace(
            host="localhost",
            port=18811,
            node_paths=["/obj/geo1/box1"],
            no_frame=False,
            no_select=True,
            no_current=True,
        )
    )

    assert result["ok"] is True
    assert result["data"]["selected"] is False
    assert result["data"]["current"] is None
    assert editor.framed is True
    assert editor.cleared is True
