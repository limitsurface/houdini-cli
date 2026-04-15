from argparse import Namespace

from houdini_cli.commands import query


class FakeParm:
    def __init__(self, name: str, at_default: bool) -> None:
        self._name = name
        self._at_default = at_default

    def name(self):
        return self._name

    def isAtDefault(self):
        return self._at_default


class FakeNodeTypeCategory:
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self):
        return self._name


class FakeNodeType:
    def __init__(self, name: str, category: str) -> None:
        self._name = name
        self._category = category

    def name(self):
        return self._name

    def category(self):
        return FakeNodeTypeCategory(self._category)


class FakeNode:
    def __init__(self, path: str, node_type: str = "null", category: str = "Sop") -> None:
        self._path = path
        self._name = path.rsplit("/", 1)[-1]
        self._type = FakeNodeType(node_type, category)
        self._children = []
        self._inputs = []
        self._outputs = []
        self._parms = []

    def path(self):
        return self._path

    def name(self):
        return self._name

    def type(self):
        return self._type

    def children(self):
        return self._children

    def inputs(self):
        return self._inputs

    def outputs(self):
        return self._outputs

    def inputConnections(self):
        connections = []
        for index, source in enumerate(self._inputs):
            if source is None:
                continue
            connections.append(FakeConnection(source, self, 0, index))
        return connections

    def parms(self):
        return self._parms

    def isDisplayFlagSet(self):
        return False

    def isRenderFlagSet(self):
        return False

    def isBypassed(self):
        return False


class FakeSession:
    def __init__(self, root: FakeNode) -> None:
        self.hou = self
        self.root = root

    def node(self, path):
        queue = [self.root]
        while queue:
            current = queue.pop(0)
            if current.path() == path:
                return current
            queue.extend(current.children())
        return None


class FakeConnection:
    def __init__(self, source: FakeNode, dest: FakeNode, output_index: int, input_index: int) -> None:
        self._source = source
        self._dest = dest
        self._output_index = output_index
        self._input_index = input_index

    def inputNode(self):
        return self._source

    def outputNode(self):
        return self._dest

    def outputIndex(self):
        return self._output_index

    def inputIndex(self):
        return self._input_index


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


def _make_tree():
    root = FakeNode("/obj", node_type="objnet", category="Manager")
    a = FakeNode("/obj/box1", node_type="box")
    b = FakeNode("/obj/null1", node_type="null")
    root._children = [a, b]
    b._inputs = [a]
    a._outputs = [b]
    b._parms = [FakeParm("scale", True), FakeParm("display", False)]
    return root, a, b


def test_handle_list(monkeypatch) -> None:
    root, _, _ = _make_tree()
    monkeypatch.setattr(query, "connect", FakeConnect(FakeSession(root)))
    monkeypatch.setattr(query, "localize", lambda value: value)

    result = query.handle_list(
        Namespace(host="localhost", port=18811, root_path="/obj", max_depth=1, max_nodes=50)
    )
    assert result["ok"] is True
    assert result["data"]["count"] == 2
    assert result["data"]["cols"] == ["p", "t", "cc", "in", "out", "f"]
    assert result["data"]["rows"] == [
        ["box1", "box", 0, 0, 1, ""],
        ["null1", "null", 0, 1, 0, ""],
    ]


def test_handle_list_truncates(monkeypatch) -> None:
    root, _, _ = _make_tree()
    monkeypatch.setattr(query, "connect", FakeConnect(FakeSession(root)))
    monkeypatch.setattr(query, "localize", lambda value: value)

    result = query.handle_list(
        Namespace(host="localhost", port=18811, root_path="/obj", max_depth=1, max_nodes=2)
    )

    assert result["ok"] is True
    assert result["data"]["count"] == 1
    assert result["meta"]["truncated"] is True


def test_handle_find(monkeypatch) -> None:
    root, _, _ = _make_tree()
    monkeypatch.setattr(query, "connect", FakeConnect(FakeSession(root)))
    monkeypatch.setattr(query, "localize", lambda value: value)

    result = query.handle_find(
        Namespace(
            host="localhost",
            port=18811,
            root_path="/obj",
            type_name="box",
            category=None,
            name=None,
            max_depth=1,
            max_nodes=50,
        )
    )
    assert result["ok"] is True
    assert result["data"]["count"] == 1
    assert result["data"]["query"] == {"type": "box"}
    assert result["data"]["rows"][0] == ["box1", "box", 0, 0, 1, ""]


def test_handle_find_by_name(monkeypatch) -> None:
    root, _, _ = _make_tree()
    monkeypatch.setattr(query, "connect", FakeConnect(FakeSession(root)))
    monkeypatch.setattr(query, "localize", lambda value: value)

    result = query.handle_find(
        Namespace(
            host="localhost",
            port=18811,
            root_path="/obj",
            type_name=None,
            category=None,
            name="NULL",
            max_depth=1,
            max_nodes=50,
        )
    )

    assert result["ok"] is True
    assert result["data"]["count"] == 1
    assert result["data"]["query"] == {"name": "NULL"}
    assert result["data"]["rows"][0][0] == "null1"


def test_handle_neighbors(monkeypatch) -> None:
    root, _, b = _make_tree()
    monkeypatch.setattr(query, "connect", FakeConnect(FakeSession(root)))
    monkeypatch.setattr(query, "localize", lambda value: value)

    result = query.handle_neighbors(
        Namespace(host="localhost", port=18811, node_path="/obj/null1", depth=1, max_nodes=50)
    )
    assert result["ok"] is True
    assert result["data"]["root"] == "/obj/null1"
    assert result["data"]["nodes"]["cols"] == ["id", "p", "t", "f"]
    assert result["data"]["nodes"]["rows"] == [
        [0, "null1", "null", ""],
        [1, "box1", "box", ""],
    ]
    assert result["data"]["edges"]["cols"] == ["src", "out", "dst", "in"]
    assert result["data"]["edges"]["rows"] == [[1, 0, 0, 0]]
