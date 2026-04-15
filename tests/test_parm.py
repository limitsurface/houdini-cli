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
        tuple_name: str | None = None,
    ) -> None:
        self._name = name
        self._path = path
        self._value = {"value": 3} if value is None else value
        self._template_type = template_type
        self._at_default = at_default
        self._tuple_name = tuple_name or name
        self._tuple_members = [self]
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

    def tuple(self):
        members = self._tuple_members
        tuple_name = self._tuple_name

        class _Tuple:
            def __init__(self, items, name: str) -> None:
                self._items = items
                self._name = name
                self.last_set_payload = None

            def __iter__(self):
                return iter(self._items)

            def __len__(self):
                return len(self._items)

            def __getitem__(self, index):
                return self._items[index]

            def name(self):
                return self._name

            def set(self, payload):
                self.last_set_payload = payload
                for item, value in zip(self._items, payload, strict=True):
                    item.last_scalar_payload = value

        return _Tuple(members, tuple_name)

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

    def parmTuple(self, path):
        if self._parm is None:
            return None
        parm_tuple = self._parm.tuple()
        if parm_tuple.name() == path.rsplit("/", 1)[-1]:
            return parm_tuple
        return None

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


def _bind_tuple(tuple_name: str, *parms: FakeParm) -> None:
    for parm in parms:
        parm._tuple_name = tuple_name
        parm._tuple_members = list(parms)


def test_handle_get_default(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_get(Namespace(host="localhost", port=18811, parm_path="/obj/x"))
    assert result["ok"] is True
    assert result["data"]["value"] == {"value": 3}


def test_handle_get_tuple_component_returns_scalar_value(monkeypatch) -> None:
    tx = FakeParm(name="tx", path="/obj/x/tx", value=[1.5, 0.0, 0.0], template_type="Float")
    ty = FakeParm(name="ty", path="/obj/x/ty", value=[1.5, 0.0, 0.0], template_type="Float")
    tz = FakeParm(name="tz", path="/obj/x/tz", value=[1.5, 0.0, 0.0], template_type="Float")
    _bind_tuple("t", tx, ty, tz)
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(tx)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_get(Namespace(host="localhost", port=18811, parm_path="/obj/x/tx"))
    assert result["ok"] is True
    assert result["data"]["value"] == 1.5


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

    result = parm.handle_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", value="hello")
    )
    assert result["ok"] is True
    assert fake_parm.last_scalar_payload == "hello"


def test_handle_set_default_scalar_uses_plain_set(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))

    result = parm.handle_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", value="4.5")
    )
    assert result["ok"] is True
    assert fake_parm.last_scalar_payload == 4.5
    assert fake_parm.last_value_payload is None


def test_handle_text_set(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "_read_text_input", lambda _value: "hello\nworld\n")

    result = parm.handle_text_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", input="snippet.txt")
    )
    assert result["ok"] is True
    assert fake_parm.last_scalar_payload == "hello\nworld\n"


def test_handle_full_set(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm, "_read_json_input", lambda _value: {"b": 2})

    result = parm.handle_full_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", input="payload.json")
    )
    assert result["ok"] is True
    assert fake_parm.last_full_payload == {"b": 2}
    assert fake_parm.last_value_payload is None


def test_handle_tuple_set(monkeypatch) -> None:
    tx = FakeParm(name="tx", path="/obj/x/tx", value=[0.0, 0.0, 0.0], template_type="Float")
    ty = FakeParm(name="ty", path="/obj/x/ty", value=[0.0, 0.0, 0.0], template_type="Float")
    tz = FakeParm(name="tz", path="/obj/x/tz", value=[0.0, 0.0, 0.0], template_type="Float")
    _bind_tuple("t", tx, ty, tz)
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(tx)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_tuple_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x/t", values=["1.5", "0", "-2"])
    )
    assert result["ok"] is True
    assert tx.last_scalar_payload == 1.5
    assert ty.last_scalar_payload == 0
    assert tz.last_scalar_payload == -2


def test_handle_node_parms_list(monkeypatch) -> None:
    tx = FakeParm(name="tx", path="/obj/x/tx", value=[1.5, 0.0, 0.0], template_type="Float", at_default=False)
    ty = FakeParm(name="ty", path="/obj/x/ty", value=[1.5, 0.0, 0.0], template_type="Float", at_default=True)
    tz = FakeParm(name="tz", path="/obj/x/tz", value=[1.5, 0.0, 0.0], template_type="Float", at_default=True)
    _bind_tuple("t", tx, ty, tz)
    fake_node = FakeNode(
        [
            FakeParm(name="dist", path="/obj/x/dist", value=0.25, template_type="Float", at_default=False),
            FakeParm(name="mode", path="/obj/x/mode", value="mult", template_type="Menu", at_default=True),
            FakeParm(name="folder1", path="/obj/x/folder1", value=1, template_type="Folder", at_default=False),
            tx,
            ty,
            tz,
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
        ["t", "Float3", [1.5, 0.0, 0.0], "n"],
    ]


def test_handle_node_parms_find(monkeypatch) -> None:
    tx = FakeParm(name="tx", path="/obj/x/tx", value=[1.5, 0.0, 0.0], template_type="Float", at_default=False)
    ty = FakeParm(name="ty", path="/obj/x/ty", value=[1.5, 0.0, 0.0], template_type="Float", at_default=True)
    tz = FakeParm(name="tz", path="/obj/x/tz", value=[1.5, 0.0, 0.0], template_type="Float", at_default=True)
    _bind_tuple("t", tx, ty, tz)
    fake_node = FakeNode(
        [
            FakeParm(name="dist", path="/obj/x/dist", value=0.25, template_type="Float", at_default=False),
            FakeParm(name="divs", path="/obj/x/divs", value=3, template_type="Int", at_default=False),
            FakeParm(name="mode", path="/obj/x/mode", value="mult", template_type="Menu", at_default=True),
            tx,
            ty,
            tz,
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


def test_handle_node_parms_find_matches_tuple_component_names(monkeypatch) -> None:
    tx = FakeParm(name="tx", path="/obj/x/tx", value=[1.5, 0.0, 0.0], template_type="Float", at_default=False)
    ty = FakeParm(name="ty", path="/obj/x/ty", value=[1.5, 0.0, 0.0], template_type="Float", at_default=True)
    tz = FakeParm(name="tz", path="/obj/x/tz", value=[1.5, 0.0, 0.0], template_type="Float", at_default=True)
    _bind_tuple("t", tx, ty, tz)
    invert = FakeParm(name="invertxform", path="/obj/x/invertxform", value=False, template_type="Toggle", at_default=True)
    fake_node = FakeNode([tx, ty, tz, invert])
    monkeypatch.setattr(parm, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(parm, "localize", lambda value: value)

    result = parm.handle_node_parms_find(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            name="tx",
            parm_type=None,
            non_default=False,
            max_parms=10,
        )
    )
    assert result["ok"] is True
    assert result["data"]["rows"] == [["t", "Float3", [1.5, 0.0, 0.0], "n"]]


def test_missing_parm_raises() -> None:
    with pytest.raises(ValueError, match="Parameter not found"):
        parm._get_parm(FakeSession(None), "/obj/missing")
