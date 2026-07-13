from argparse import Namespace

import pytest

from houdini_cli.commands import (
    node_parms,
    parm,
    parm_common,
    parm_refs,
    parm_templates,
    parm_values,
)


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
        raw=None,
        expression: str | None = None,
        references=None,
    ) -> None:
        self._name = name
        self._path = path
        self._value = {"value": 3} if value is None else value
        self._template_type = template_type
        self._at_default = at_default
        self._tuple_name = tuple_name or name
        self._tuple_members = [self]
        self._raw = value if raw is None else raw
        self._expression = expression
        self._references = references or []
        self.last_value_payload = None
        self.last_full_payload = None
        self.last_scalar_payload = None
        self._node = None

    def valueAsData(self):
        return self._value

    def asData(self, brief=False):
        return {"full": True, "brief": brief}

    def name(self):
        return self._name

    def path(self):
        return self._path

    def node(self):
        return self._node

    def rawValue(self):
        return self._raw

    def expression(self):
        if self._expression is None:
            raise RuntimeError("no expression")
        return self._expression

    def expressionLanguage(self):
        class _Language:
            def name(self):
                return "Hscript"

        return _Language()

    def references(self):
        return self._references

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


class FakeConnection:
    def __init__(self):
        self.executed = None
        self.evaluated = None
        self.eval_result = {
            "template_name": "processing_scale",
            "default": (0.75,),
            "library": "test.hda",
        }

    def execute(self, source):
        self.executed = source

    def eval(self, expression):
        self.evaluated = expression
        return self.eval_result


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
    def __init__(self, parms: list[FakeParm], children=None) -> None:
        self._parms = parms
        self._children = children or []
        for item in self._parms:
            item._node = self

    def parms(self):
        return self._parms

    def allSubChildren(self):
        return self._children

    def parm(self, name: str):
        for item in self._parms:
            if item.name() == name:
                return item
        return None

    def node(self, path: str):
        return None


class FakeTargetParm:
    def __init__(self, path: str) -> None:
        self._path = path

    def path(self):
        return self._path


def _bind_tuple(tuple_name: str, *parms: FakeParm) -> None:
    for item in parms:
        item._tuple_name = tuple_name
        item._tuple_members = list(parms)


def test_handle_get_default(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm_common, "localize", lambda value: value)
    monkeypatch.setattr(parm_values, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm_values, "localize", lambda value: value)

    result = parm.handle_get(Namespace(host="localhost", port=18811, parm_path="/obj/x"))
    assert result["ok"] is True
    assert result["data"]["value"] == {"value": 3}


def test_handle_get_tuple_component_returns_scalar_value(monkeypatch) -> None:
    tx = FakeParm(name="tx", path="/obj/x/tx", value=[1.5, 0.0, 0.0], template_type="Float")
    ty = FakeParm(name="ty", path="/obj/x/ty", value=[1.5, 0.0, 0.0], template_type="Float")
    tz = FakeParm(name="tz", path="/obj/x/tz", value=[1.5, 0.0, 0.0], template_type="Float")
    _bind_tuple("t", tx, ty, tz)
    monkeypatch.setattr(parm_common, "localize", lambda value: value)
    monkeypatch.setattr(parm_values, "connect", FakeConnect(FakeSession(tx)))
    monkeypatch.setattr(parm_values, "localize", lambda value: value)

    result = parm.handle_get(Namespace(host="localhost", port=18811, parm_path="/obj/x/tx"))
    assert result["ok"] is True
    assert result["data"]["value"] == 1.5


def test_handle_full(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm_values, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm_values, "localize", lambda value: value)

    result = parm.handle_full(Namespace(host="localhost", port=18811, parm_path="/obj/x"))
    assert result["ok"] is True
    assert result["data"]["value"] == {"full": True, "brief": False}


def test_handle_menu(monkeypatch) -> None:
    fake_parm = FakeParm()
    fake_parm.menuItems = lambda: ("poly", "mesh")
    fake_parm.menuLabels = lambda: ("Polygon", "Mesh")
    fake_parm.evalAsString = lambda: "poly"
    monkeypatch.setattr(parm_values, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm_values, "localize", lambda value: value)

    result = parm.handle_menu(Namespace(host="localhost", port=18811, parm_path="/obj/x"))
    assert result["ok"] is True
    assert result["data"]["current_value"] == "poly"
    assert result["data"]["menu_items"] == [
        {"token": "poly", "label": "Polygon"},
        {"token": "mesh", "label": "Mesh"},
    ]


def test_handle_set_default(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm_values, "connect", FakeConnect(FakeSession(fake_parm)))

    result = parm.handle_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", value="hello")
    )
    assert result["ok"] is True
    assert fake_parm.last_scalar_payload == "hello"


def test_handle_set_default_scalar_uses_plain_set(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm_values, "connect", FakeConnect(FakeSession(fake_parm)))

    result = parm.handle_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", value="4.5")
    )
    assert result["ok"] is True
    assert fake_parm.last_scalar_payload == 4.5
    assert fake_parm.last_value_payload is None


def test_definition_default_executes_entire_edit_inside_houdini(monkeypatch) -> None:
    session = FakeSession(None)
    session.connection = FakeConnection()
    monkeypatch.setattr(parm_templates, "connect", FakeConnect(session))
    monkeypatch.setattr(parm_templates, "localize", lambda value: value)

    result = parm.handle_default_set(
        Namespace(
            host="localhost",
            port=18811,
            parm_path="/obj/copnet1/ntsc_vhs1/processing_scale",
            target="definition",
            current=False,
            value="0.75",
        )
    )

    assert result["ok"] is True
    assert result["data"]["default"] == (0.75,)
    assert "executeInMainThreadWithResult" in session.connection.executed
    assert "processing_scale" in session.connection.evaluated


def test_handle_text_set(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm_values, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm_values, "read_text_input", lambda _value: "hello\nworld\n")

    result = parm.handle_text_set(
        Namespace(host="localhost", port=18811, parm_path="/obj/x", input="snippet.txt")
    )
    assert result["ok"] is True
    assert fake_parm.last_scalar_payload == "hello\nworld\n"


def test_handle_full_set(monkeypatch) -> None:
    fake_parm = FakeParm()
    monkeypatch.setattr(parm_values, "connect", FakeConnect(FakeSession(fake_parm)))
    monkeypatch.setattr(parm_values, "read_json_input", lambda _value: {"b": 2})

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
    monkeypatch.setattr(parm_common, "localize", lambda value: value)
    monkeypatch.setattr(parm_values, "connect", FakeConnect(FakeSession(tx)))
    monkeypatch.setattr(parm_values, "localize", lambda value: value)

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
    monkeypatch.setattr(parm_common, "localize", lambda value: value)
    monkeypatch.setattr(node_parms, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(node_parms, "localize", lambda value: value)

    result = parm.handle_node_parms_list(
        Namespace(host="localhost", port=18811, node_path="/obj/x", non_default=False, max_parms=10, values=True)
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
    monkeypatch.setattr(parm_common, "localize", lambda value: value)
    monkeypatch.setattr(node_parms, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(node_parms, "localize", lambda value: value)

    result = parm.handle_node_parms_find(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            name="di",
            parm_type=None,
            non_default=True,
            max_parms=10,
            values=True,
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
    monkeypatch.setattr(parm_common, "localize", lambda value: value)
    monkeypatch.setattr(node_parms, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(node_parms, "localize", lambda value: value)

    result = parm.handle_node_parms_find(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            name="tx",
            parm_type=None,
            non_default=False,
            max_parms=10,
            values=True,
        )
    )
    assert result["ok"] is True
    assert result["data"]["rows"] == [["t", "Float3", [1.5, 0.0, 0.0], "n"]]


def test_node_parms_truncates_long_strings_unless_requested(monkeypatch) -> None:
    source = "x" * 200
    fake_node = FakeNode(
        [FakeParm(name="kernelcode", path="/obj/x/kernelcode", value=source, template_type="String")]
    )
    monkeypatch.setattr(parm_common, "localize", lambda value: value)
    monkeypatch.setattr(node_parms, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(node_parms, "localize", lambda value: value)

    compact = parm.handle_node_parms_list(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            non_default=False,
            max_parms=10,
            full_values=False,
            values=True,
        )
    )
    full = parm.handle_node_parms_list(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            non_default=False,
            max_parms=10,
            full_values=True,
            values=True,
        )
    )

    assert compact["data"]["rows"][0][2].endswith("...")
    assert len(compact["data"]["rows"][0][2]) == 120
    assert full["data"]["rows"][0][2] == source


def test_node_parms_value_mode_none_does_not_read_values(monkeypatch) -> None:
    fake_parm = FakeParm(name="dist", path="/obj/x/dist", value=0.25, template_type="Float")
    fake_parm.valueAsData = lambda: (_ for _ in ()).throw(AssertionError("value evaluated"))
    fake_node = FakeNode([fake_parm])
    monkeypatch.setattr(parm_common, "localize", lambda value: value)
    monkeypatch.setattr(node_parms, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(node_parms, "localize", lambda value: value)

    result = parm.handle_node_parms_list(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            name=None,
            parm_type=None,
            non_default=False,
            max_parms=10,
            full_values=False,
            value_mode="none",
        )
    )

    assert result["data"]["rows"] == [["dist", "Float", None, "n"]]
    assert result["meta"]["value_mode"] == "none"


def test_node_parms_summary_bounds_long_strings_and_reports_total(monkeypatch) -> None:
    fake_node = FakeNode(
        [
            FakeParm(name="first", path="/obj/x/first", value="x" * 300, template_type="String"),
            FakeParm(name="second", path="/obj/x/second", value=2, template_type="Int"),
        ]
    )
    monkeypatch.setattr(parm_common, "localize", lambda value: value)
    monkeypatch.setattr(node_parms, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(node_parms, "localize", lambda value: value)

    result = parm.handle_node_parms_list(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            name=None,
            parm_type=None,
            non_default=False,
            max_parms=1,
            full_values=False,
            value_mode="summary",
        )
    )

    value = result["data"]["rows"][0][2]
    assert value["kind"] == "string"
    assert value["length"] == 300
    assert result["meta"] == {
        "value_mode": "summary",
        "total": 2,
        "truncated": True,
        "max_parms": 1,
    }


def test_handle_find_searches_raw_expression_and_resolved_targets(monkeypatch) -> None:
    external_target = FakeTargetParm("/obj/geo1/copnet1/controller/amount")
    fake_node = FakeNode(
        [
            FakeParm(
                name="raw_path",
                path="/obj/x/raw_path",
                value="/obj/geo1/copnet1",
                template_type="String",
            ),
            FakeParm(
                name="expr_path",
                path="/obj/x/expr_path",
                value=0.0,
                expression='ch("../gain")',
                template_type="Float",
            ),
            FakeParm(
                name="ref_path",
                path="/obj/x/ref_path",
                value=1.0,
                references=[external_target],
                template_type="Float",
            ),
        ]
    )
    monkeypatch.setattr(parm_refs, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(parm_refs, "localize", lambda value: value)

    raw = parm.handle_find(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            query="copnet1",
            raw=True,
            expressions=False,
            resolved_targets=False,
            max_matches=10,
        )
    )
    expr = parm.handle_find(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            query="../gain",
            raw=False,
            expressions=True,
            resolved_targets=False,
            max_matches=10,
        )
    )
    target = parm.handle_find(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            query="controller",
            raw=False,
            expressions=False,
            resolved_targets=True,
            max_matches=10,
        )
    )

    assert raw["data"]["items"][0]["matches"] == ["raw"]
    assert raw["data"]["items"][0]["raw"] == "/obj/geo1/copnet1"
    assert expr["data"]["items"][0]["matches"] == ["expression"]
    assert expr["data"]["items"][0]["expression"] == 'ch("../gain")'
    assert target["data"]["items"][0]["matches"] == ["resolved_target"]
    assert target["data"]["items"][0]["resolved_targets"] == ["/obj/geo1/copnet1/controller/amount"]


def test_handle_refs_marks_external_targets(monkeypatch) -> None:
    fake_node = FakeNode(
        [
            FakeParm(
                name="internal",
                path="/obj/x/internal",
                references=[FakeTargetParm("/obj/x/controller/amount")],
            ),
            FakeParm(
                name="external",
                path="/obj/x/external",
                references=[FakeTargetParm("/obj/geo1/copnet1/controller/amount")],
            ),
        ]
    )
    monkeypatch.setattr(parm_refs, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(parm_refs, "localize", lambda value: value)

    result = parm.handle_refs(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            external_to="/obj/x",
            recursive=False,
            max_refs=10,
        )
    )

    assert result["data"]["items"] == [
        {
            "from_parm": "/obj/x/internal",
            "to_parm": "/obj/x/controller/amount",
            "external": False,
        },
        {
            "from_parm": "/obj/x/external",
            "to_parm": "/obj/geo1/copnet1/controller/amount",
            "external": True,
        },
    ]


def test_handle_refs_recursive_includes_child_nodes(monkeypatch) -> None:
    child = FakeNode(
        [
            FakeParm(
                name="external",
                path="/obj/x/child/external",
                references=[FakeTargetParm("/obj/geo1/controller/amount")],
            )
        ]
    )
    fake_node = FakeNode([], children=[child])
    monkeypatch.setattr(parm_refs, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(parm_refs, "localize", lambda value: value)

    result = parm.handle_refs(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            external_to="/obj/x",
            recursive=True,
            max_refs=10,
        )
    )

    assert result["data"]["recursive"] is True
    assert result["data"]["items"] == [
        {
            "from_parm": "/obj/x/child/external",
            "to_parm": "/obj/geo1/controller/amount",
            "external": True,
        }
    ]


def test_handle_refs_resolves_channel_refs_when_hom_references_are_empty(monkeypatch) -> None:
    fake_node = FakeNode(
        [
            FakeParm(name="source", path="/obj/x/source", expression='ch("target")'),
            FakeParm(name="target", path="/obj/x/target"),
        ]
    )
    monkeypatch.setattr(parm_refs, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(parm_refs, "localize", lambda value: value)

    result = parm.handle_refs(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/x",
            external_to="/obj/x",
            recursive=False,
            max_refs=10,
        )
    )

    assert result["data"]["items"] == [
        {
            "from_parm": "/obj/x/source",
            "to_parm": "/obj/x/target",
            "external": False,
        }
    ]


def test_handle_find_does_not_match_only_containing_parm_path(monkeypatch) -> None:
    fake_node = FakeNode(
        [
            FakeParm(
                name="scale",
                path="/obj/geo1/copnet1/asset1/scale",
                value=1.0,
                template_type="Float",
            )
        ]
    )
    monkeypatch.setattr(parm_refs, "connect", FakeConnect(FakeSession(None, fake_node)))
    monkeypatch.setattr(parm_refs, "localize", lambda value: value)

    result = parm.handle_find(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/geo1/copnet1/asset1",
            query="copnet1",
            raw=False,
            expressions=False,
            resolved_targets=False,
            max_matches=10,
        )
    )

    assert result["data"]["items"] == []


def test_missing_parm_raises() -> None:
    with pytest.raises(ValueError, match="Parameter not found"):
        parm_common.get_parm(FakeSession(None), "/obj/missing")
