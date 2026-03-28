from types import SimpleNamespace

import pytest
from rpyc.core.async_ import AsyncResultTimeout

from houdini_cli.transport import rpyc as transport


class FakeConnection:
    def __init__(self) -> None:
        self._config = {"sync_request_timeout": 20.0}
        self.modules = SimpleNamespace(hou="hou")
        self.closed = False

    def close(self):
        self.closed = True


def test_sync_request_timeout_restores_previous_value() -> None:
    session = transport.HoudiniSession(connection=FakeConnection(), hou="hou")

    with transport.sync_request_timeout(session, 7.5):
        assert session.connection._config["sync_request_timeout"] == 7.5

    assert session.connection._config["sync_request_timeout"] == 20.0


def test_localize_wraps_async_timeout(monkeypatch) -> None:
    monkeypatch.setattr(transport, "obtain", lambda value: (_ for _ in ()).throw(AsyncResultTimeout("expired")))

    with pytest.raises(transport.TransportTimeoutError, match="retrieving remote Houdini data"):
        transport.localize("x")


def test_connect_wraps_connection_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        transport.rpyc.classic,
        "connect",
        lambda host, port: (_ for _ in ()).throw(ConnectionRefusedError("refused")),
    )

    with pytest.raises(transport.TransportConnectionError, match="Failed to connect to Houdini"):
        with transport.connect("localhost", 18811):
            pass


def test_connect_uses_override_sync_timeout(monkeypatch) -> None:
    fake_connection = FakeConnection()
    monkeypatch.setattr(transport.rpyc.classic, "connect", lambda host, port: fake_connection)

    with transport.connect("localhost", 18811, sync_request_timeout_seconds=9.0) as session:
        assert session.connection._config["sync_request_timeout"] == 9.0

    assert fake_connection.closed is True
