import pytest

from houdini_cli.remote import RemoteModule, python_literal
from houdini_cli.remote.node_references import NODE_REFERENCE_REMOTE


class FakeConnection:
    def __init__(self) -> None:
        self.executed = []
        self.evaluated = []

    def execute(self, source):
        self.executed.append(source)

    def eval(self, expression):
        self.evaluated.append(expression)
        return {"expression": expression}


def test_python_literal_encodes_transport_safe_structures() -> None:
    assert python_literal({"path": "/obj/a'b", "flags": [True, None], "point": (1, 2.5)}) == (
        "{'path': \"/obj/a'b\", 'flags': [True, None], 'point': (1, 2.5)}"
    )


def test_python_literal_rejects_unsupported_or_non_finite_values() -> None:
    with pytest.raises(TypeError, match="object"):
        python_literal(object())
    with pytest.raises(ValueError, match="finite"):
        python_literal(float("inf"))


def test_remote_module_installs_source_and_evaluates_registered_entrypoint() -> None:
    module = RemoteModule(
        namespace="test_remote",
        source="def _houdini_cli_test_remote(path, enabled): return path, enabled",
        entrypoints={"inspect": "_houdini_cli_test_remote"},
    )
    connection = FakeConnection()

    result = module.evaluate(connection, "inspect", "/obj/test", True)

    assert connection.executed == [module.source]
    assert connection.evaluated == ["_houdini_cli_test_remote('/obj/test', True)"]
    assert result == {"expression": connection.evaluated[0]}


def test_remote_module_rejects_unknown_entrypoint() -> None:
    module = RemoteModule(
        namespace="test_remote",
        source="def _houdini_cli_test_remote(): return None",
        entrypoints={"inspect": "_houdini_cli_test_remote"},
    )

    with pytest.raises(KeyError, match="missing"):
        module.call("missing")


def test_node_reference_remote_builds_registered_payload_call() -> None:
    assert NODE_REFERENCE_REMOTE.call("payload", "/obj/geo1/asset1", True) == (
        "_houdini_cli_node_reference_payload('/obj/geo1/asset1', True)"
    )
