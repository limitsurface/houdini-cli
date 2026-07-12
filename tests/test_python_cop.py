from types import SimpleNamespace

import pytest

from houdini_cli.commands import python_cop


def binding(**overrides):
    values = {
        "name": "", "type": "float", "portname": "", "readable": True,
        "writeable": False, "optional": False, "layertype": "floatn", "vdbtype": "any",
    }
    values.update(overrides)
    return values


def test_desired_python_cop_ports_and_bindings() -> None:
    bindings = [
        binding(name="mask", type="layer", portname="mask", layertype="float", optional=True),
        binding(name="result", type="layer", portname="result", layertype="float4", readable=False, writeable=True),
        binding(name="path", type="string"),
        binding(name="gain", type="float"),
    ]

    assert python_cop.desired_ports(bindings, output=False) == [
        {"name": "mask", "type": "float", "optional": True}
    ]
    assert python_cop.desired_ports(bindings, output=True) == [
        {"name": "result", "type": "float4"}
    ]
    assert python_cop.desired_binding_rows(bindings) == [
        {"name": "path", "type": "string"},
        {"name": "gain", "type": "float"},
    ]


class Source:
    def path(self):
        return "/obj/cops/source"


class Connection:
    def __init__(self, index):
        self.index = index
        self.source = Source()

    def inputIndex(self):
        return self.index

    def inputNode(self):
        return self.source

    def outputIndex(self):
        return 0


class ConnectionNode:
    def __init__(self):
        self.connections = [Connection(0)]
        self.set_calls = []

    def inputConnections(self):
        return tuple(self.connections)

    def setInput(self, index, source, output_index=0):
        self.set_calls.append((index, source, output_index))
        self.connections = [row for row in self.connections if row.inputIndex() != index]
        if source is not None:
            row = Connection(index)
            row.source = source
            self.connections.append(row)


def test_restore_connections_uses_port_name_after_reorder() -> None:
    node = ConnectionNode()
    captured = [{"name": "src", "from_path": "/obj/cops/source", "from_output_index": 0, "source_node": node.connections[0].source}]

    restored, dropped = python_cop.restore_connections(
        node,
        [{"name": "mask"}, {"name": "src"}],
        captured,
    )

    assert dropped == []
    assert restored[0]["to_input_index"] == 1
    assert any(call[0] == 1 and call[1] is not None for call in node.set_calls)


def test_require_python_cop_rejects_other_nodes(monkeypatch) -> None:
    node = SimpleNamespace(
        type=lambda: SimpleNamespace(category=lambda: SimpleNamespace(name=lambda: "Sop")),
        parm=lambda _name: None,
        path=lambda: "/obj/geo1/python1",
    )
    monkeypatch.setattr(python_cop, "localize", lambda value: value)

    with pytest.raises(ValueError, match="not a supported Python COP"):
        python_cop.require_python_cop(node)
