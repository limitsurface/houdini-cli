from argparse import Namespace

import pytest

from houdini_cli.commands import nodetype


class FakeNodeType:
    def __init__(
        self,
        name,
        description,
        *,
        icon="SOP_default",
        hidden=False,
        deprecated=False,
        namespace_order=None,
        min_inputs=0,
        max_inputs=1,
        is_generator=False,
    ) -> None:
        self._name = name
        self._description = description
        self._icon = icon
        self._hidden = hidden
        self._deprecated = deprecated
        self._namespace_order = namespace_order or [name]
        self._min_inputs = min_inputs
        self._max_inputs = max_inputs
        self._is_generator = is_generator

    def name(self):
        return self._name

    def description(self):
        return self._description

    def icon(self):
        return self._icon

    def hidden(self):
        return self._hidden

    def deprecated(self):
        return self._deprecated

    def namespaceOrder(self):
        return self._namespace_order

    def minNumInputs(self):
        return self._min_inputs

    def maxNumInputs(self):
        return self._max_inputs

    def isGenerator(self):
        return self._is_generator


class FakeCategory:
    def __init__(self, name, node_types) -> None:
        self._name = name
        self._node_types = node_types

    def name(self):
        return self._name

    def nodeTypes(self):
        return self._node_types


class FakeHou:
    def __init__(self, categories) -> None:
        self._categories = categories

    def objNodeTypeCategory(self):
        return self._categories["obj"]

    def sopNodeTypeCategory(self):
        return self._categories["sop"]

    def cop2NodeTypeCategory(self):
        return self._categories["cop"]

    def vopNodeTypeCategory(self):
        return self._categories["vop"]

    def ropNodeTypeCategory(self):
        return self._categories["rop"]

    def lopNodeTypeCategory(self):
        return self._categories["lop"]

    def dopNodeTypeCategory(self):
        return self._categories["dop"]

    def shopNodeTypeCategory(self):
        return self._categories["shop"]


class FakeSession:
    def __init__(self, hou) -> None:
        self.hou = hou


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


def _fake_categories():
    sop_types = {
        "attribwrangle": FakeNodeType(
            "attribwrangle",
            "Attribute Wrangle",
            icon="SOP_attribwrangle",
            min_inputs=0,
            max_inputs=4,
        ),
        "box": FakeNodeType("box", "Box", icon="SOP_box", is_generator=True),
        "kinefx::rigdoctor": FakeNodeType(
            "kinefx::rigdoctor",
            "Rig Doctor",
            icon="SOP_kinefx-rigdoctor",
            min_inputs=1,
            max_inputs=1,
        ),
    }
    empty = FakeCategory("Empty", {})
    return {
        "obj": empty,
        "sop": FakeCategory("Sop", sop_types),
        "cop": empty,
        "vop": empty,
        "rop": empty,
        "lop": empty,
        "dop": empty,
        "shop": empty,
    }


def test_handle_list(monkeypatch) -> None:
    monkeypatch.setattr(nodetype, "connect", FakeConnect(FakeSession(FakeHou(_fake_categories()))))

    result = nodetype.handle_list(Namespace(host="localhost", port=18811, category="sop", limit=2))

    assert result["ok"] is True
    assert result["data"]["category"] == "sop"
    assert result["data"]["count"] == 2
    assert result["data"]["items"][0] == {"key": "attribwrangle", "description": "Attribute Wrangle"}
    assert result["meta"] == {
        "truncated": True,
        "limit": 2,
        "total_matches": 3,
        "next_hint": "Refine with --query, --prefix, or increase --limit",
    }


def test_handle_find_query(monkeypatch) -> None:
    monkeypatch.setattr(nodetype, "connect", FakeConnect(FakeSession(FakeHou(_fake_categories()))))

    result = nodetype.handle_find(
        Namespace(host="localhost", port=18811, category="sop", query="doctor", prefix=None, limit=50)
    )

    assert result["ok"] is True
    assert result["data"]["count"] == 1
    assert result["data"]["items"][0]["key"] == "kinefx::rigdoctor"
    assert result["meta"]["truncated"] is False


def test_handle_find_prefix(monkeypatch) -> None:
    monkeypatch.setattr(nodetype, "connect", FakeConnect(FakeSession(FakeHou(_fake_categories()))))

    result = nodetype.handle_find(
        Namespace(host="localhost", port=18811, category="sop", query=None, prefix="attrib", limit=50)
    )

    assert result["ok"] is True
    assert result["data"]["items"] == [{"key": "attribwrangle", "description": "Attribute Wrangle"}]


def test_handle_find_requires_filter(monkeypatch) -> None:
    monkeypatch.setattr(nodetype, "connect", FakeConnect(FakeSession(FakeHou(_fake_categories()))))

    with pytest.raises(ValueError, match="requires --query and/or --prefix"):
        nodetype.handle_find(
            Namespace(host="localhost", port=18811, category="sop", query=None, prefix=None, limit=50)
        )


def test_handle_find_no_matches(monkeypatch) -> None:
    monkeypatch.setattr(nodetype, "connect", FakeConnect(FakeSession(FakeHou(_fake_categories()))))

    result = nodetype.handle_find(
        Namespace(host="localhost", port=18811, category="sop", query="missing", prefix=None, limit=50)
    )

    assert result["ok"] is True
    assert result["data"]["count"] == 0
    assert result["data"]["items"] == []
    assert result["meta"]["truncated"] is False


def test_handle_get(monkeypatch) -> None:
    monkeypatch.setattr(nodetype, "connect", FakeConnect(FakeSession(FakeHou(_fake_categories()))))

    result = nodetype.handle_get(
        Namespace(host="localhost", port=18811, category="sop", type_key="attribwrangle")
    )

    assert result["ok"] is True
    assert result["data"] == {
        "key": "attribwrangle",
        "name": "attribwrangle",
        "description": "Attribute Wrangle",
        "category": "sop",
        "icon": "SOP_attribwrangle",
        "hidden": False,
        "deprecated": False,
        "namespace_order": ["attribwrangle"],
        "min_num_inputs": 0,
        "max_num_inputs": 4,
        "is_generator": False,
    }


def test_handle_get_missing_type(monkeypatch) -> None:
    monkeypatch.setattr(nodetype, "connect", FakeConnect(FakeSession(FakeHou(_fake_categories()))))

    with pytest.raises(ValueError, match="Node type not found"):
        nodetype.handle_get(Namespace(host="localhost", port=18811, category="sop", type_key="missing"))


def test_limit_must_be_positive(monkeypatch) -> None:
    monkeypatch.setattr(nodetype, "connect", FakeConnect(FakeSession(FakeHou(_fake_categories()))))

    with pytest.raises(ValueError, match="Limit must be positive"):
        nodetype.handle_list(Namespace(host="localhost", port=18811, category="sop", limit=0))
