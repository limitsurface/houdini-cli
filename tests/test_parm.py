from argparse import Namespace

import pytest

from houdini_cli.commands import parm


class FakeParm:
    def __init__(
        self,
        *,
        name: str = "x",
        path: str = "/obj/x",
        value=None,
        template_type: str = "Float",
        at_default: bool = False,
    ) -> None:
        self._name = name
        self._path = path
        self._value = {"value": 3} if value is None else value
        self._template_type = template_type
        self._at_default = at_default
        self.last_value_payload = None
        self.last_full_payload = None
        self.last_scalar_payload = None

    def valueAsData(self):
        return self._value

    def asData(self, brief=False):
        return {"full": True, "brief": brief}

    def name(self):
        return self._name

    def path(self):
        return self._path

    def parmTemplate(self):
        class _TemplateType:
            def __init__(self, name: str) -> None:
                self._name = name

            def name(self):
                return self._name

        class _Template:
            def __init__(self, template_type: str) -> None:
                self._template_type = template_type

            def type(self):
                return _TemplateType(self._template_type)

        return _Template(self._template_type)

    def isAtDefault(self):
        return self._at_default

    def setValueFromData(self, payload):
        self.last_value_payload = payload

    def setFromData(self, payload):
        self.last_full_payload = payload

    def set(self, payload):
        self.last_scalar_payload = payload


class FakeSession:
    def __init__(self, fake_parm: FakeParm | None, fake_node=None) -> None:
        self.hou = self
        self._parm = fake_parm
        self._node = fake_node

    def parm(self, path):
        return self._parm

    def node(self, path):
        return self._node


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


class FakeNode:
    def __init__(self, parms: list[FakeParm]) -> None:
        self._parms = parms

    def parms(self):
        return self._parms


def test_handle_get_default(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_get(Namespace(host="localhost", port=18811, parm_path="/obj/x"))
    assert result["ok"] is True
    assert result["data"]["value"] == {"value": 3}


def test_handle_full(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_full(Namespace(host="localhost", port=18811, parm_path="/obj/x"))
    assert result["ok"] is True
    assert result["data"]["value"] == {"full": True, "brief": False}


def test_handle_menu(monkeypatch) -> None:
    fake_parm = FakeParm()
    fake_parm.menuItems = lambda: ("poly", "mesh")
    fake_parm.menuLabels = lambda: ("Polygon", "Mesh")
    fake_parm.evalAsString = lambda: "poly"
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_menu(Namespace(host="localhost", port=18811, parm_path="/obj/x"))
    assert result["ok"] is True
    assert result["data"]["current_value"] == "poly"
    assert result["data"]["menu_items"] == [
        {"token": "poly", "label": "Polygon"},
        {"token": "mesh", "label": "Mesh"},
    ]


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
    assert fake_parm.last_scalar_payload is None


def test_handle_set_default_scalar_uses_plain_set(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "load_json_input", lambda raw: 4.5)

    result = parm.handle_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", full=False, json="4.5")
    )
    assert result["ok"] is True
    assert fake_parm.last_scalar_payload == 4.5
    assert fake_parm.last_value_payload is None


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


def test_handle_node_parms_list(monkeypatch) -> None:
    fake_node = FakeNode(
        [
            FakeParm(name="dist", path="/obj/x/dist", value=0.25, template_type="Float", at_default=False),
            FakeParm(name="mode", path="/obj/x/mode", value="mult", template_type="Menu", at_default=True),
            FakeParm(name="folder1", path="/obj/x/folder1", value=1, template_type="Folder", at_default=False),
        ]
    )
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_node_parms_list(
        Namespace(host="localhost", port=18811, node_path="/obj/x", non_default=False, max_parms=10)
    )
    assert result["ok"] is True
    assert result["data"]["cols"] == ["p", "t", "v", "f"]
    assert result["data"]["rows"] == [
        ["dist", "Float", 0.25, "n"],
        ["mode", "Menu", "mult", ""],
    ]


def test_handle_node_parms_find(monkeypatch) -> None:
    fake_node = FakeNode(
        [
            FakeParm(name="dist", path="/obj/x/dist", value=0.25, template_type="Float", at_default=False),
            FakeParm(name="divs", path="/obj/x/divs", value=3, template_type="Int", at_default=False),
            FakeParm(name="mode", path="/obj/x/mode", value="mult", template_type="Menu", at_default=True),
        ]
    )
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_node_parms_find(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            name="di",
            parm_type=None,
            non_default=True,
            max_parms=10,
        )
    )
    assert result["ok"] is True
    assert result["data"]["query"] == {"name": "di", "non_default": True}
    assert result["data"]["rows"] == [["dist", "Float", 0.25, "n"], ["divs", "Int", 3, "n"]]


def test_missing_parm_raises() -> None:
    with pytest.raises(ValueError, match="Parameter not found"):
        parm._get_parm(FakeSession(None), "/obj/missing")
