from argparse import Namespace

import pytest

from houdini_cli.commands import parm


class FakeParm:
    def __init__(self) -> None:
        self.last_value_payload = None
        self.last_full_payload = None

    def valueAsData(self):
        return {"value": 3}

    def asData(self, brief=False):
        return {"full": True, "brief": brief}

    def setValueFromData(self, payload):
        self.last_value_payload = payload

    def setFromData(self, payload):
        self.last_full_payload = payload


class FakeSession:
    def __init__(self, fake_parm: FakeParm | None) -> None:
        self.hou = self
        self._parm = fake_parm

    def parm(self, path):
        return self._parm


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


def test_handle_get_default(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_get(Namespace(host="localhost", port=18811, parm_path="/obj/x", full=False))
    assert result["ok"] is True
    assert result["data"]["value"] == {"value": 3}


def test_handle_get_full(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_get(Namespace(host="localhost", port=18811, parm_path="/obj/x", full=True))
    assert result["ok"] is True
    assert result["data"]["value"] == {"full": True, "brief": False}


def test_handle_set_default(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "load_json_input", lambda raw: {"a": 1})

    result = parm.handle_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", full=False, json='{"a":1}')
    )
    assert result["ok"] is True
    assert fake_parm.last_value_payload == {"a": 1}
    assert fake_parm.last_full_payload is None


def test_handle_set_full(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "load_json_input", lambda raw: {"b": 2})

    result = parm.handle_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", full=True, json='{"b":2}')
    )
    assert result["ok"] is True
    assert fake_parm.last_full_payload == {"b": 2}
    assert fake_parm.last_value_payload is None


def test_missing_parm_raises() -> None:
    with pytest.raises(ValueError, match="Parameter not found"):
        parm._get_parm(FakeSession(None), "/obj/missing")
