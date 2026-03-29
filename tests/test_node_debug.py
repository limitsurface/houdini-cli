from argparse import Namespace

from houdini_cli.commands import node


class FakeConnection:
    def __init__(self, source, dest) -> None:
        self._source = source
        self._dest = dest

    def inputNode(self):
        return self._source

    def outputNode(self):
        return self._dest

    def outputIndex(self):
        return 0

    def inputIndex(self):
        return 1

    def inputName(self):
        return "src"

    def inputLabel(self):
        return "Source"

    def outputName(self):
        return "input1"

    def outputLabel(self):
        return "Input 1"


class FakeNode:
    def __init__(self, path="/obj/test") -> None:
        self._path = path
        self._connections = []

    def path(self):
        return self._path

    def errors(self):
        return ("bad cook",)

    def warnings(self):
        return ("be careful",)

    def messages(self):
        return ("heads up",)

    def inputConnections(self):
        return self._connections

    def outputConnections(self):
        return self._connections


class FakeSession:
    def __init__(self, node_obj) -> None:
        self.hou = self
        self.node_obj = node_obj

    def node(self, path):
        return self.node_obj if path == self.node_obj.path() else None


class FakeConnect:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self, host, port):
        class _Ctx:
            def __enter__(inner_self):
                return self.session

            def __exit__(inner_self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_handle_errors(monkeypatch) -> None:
    fake_node = FakeNode()
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession(fake_node)))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_errors(
        Namespace(host="localhost", port=18811, node_paths=["/obj/test"])
    )

    assert result["ok"] is True
    assert result["data"]["items"][0]["errors"] == ["bad cook"]
    assert result["data"]["items"][0]["warnings"] == ["be careful"]
    assert result["data"]["items"][0]["messages"] == ["heads up"]


def test_handle_connections(monkeypatch) -> None:
    source = FakeNode("/obj/src")
    dest = FakeNode("/obj/test")
    dest._connections = [FakeConnection(source, dest)]
    monkeypatch.setattr(node, "connect", FakeConnect(FakeSession(dest)))
    monkeypatch.setattr(node, "localize", lambda value: value)

    result = node.handle_connections(
        Namespace(host="localhost", port=18811, node_path="/obj/test")
    )

    assert result["ok"] is True
    assert result["data"]["inputs"][0]["from_path"] == "/obj/src"
    assert result["data"]["inputs"][0]["to_path"] == "/obj/test"
    assert result["data"]["inputs"][0]["from_output_name"] == "src"
    assert result["data"]["inputs"][0]["to_input_name"] == "input1"
