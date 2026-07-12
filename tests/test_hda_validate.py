from houdini_cli.commands import hda_validate, parm_refs


class FakeLanguage:
    def name(self):
        return "Hscript"


class FakeParm:
    def __init__(self, node, name: str, expression: str | None = None) -> None:
        self._node = node
        self._name = name
        self._expression = expression

    def node(self):
        return self._node

    def name(self):
        return self._name

    def path(self):
        return f"{self._node.path()}/{self._name}"

    def rawValue(self):
        return self._expression or ""

    def expression(self):
        if self._expression is None:
            raise RuntimeError("no expression")
        return self._expression

    def expressionLanguage(self):
        return FakeLanguage()

    def references(self):
        return []

    def tuple(self):
        return self

    def parmTemplate(self):
        class _Type:
            def name(self):
                return "Float"

        class _Template:
            def type(self):
                return _Type()

        return _Template()


class FakeNode:
    def __init__(self, path: str) -> None:
        self._path = path
        self._parms = {}
        self._children = {}

    def path(self):
        return self._path

    def add_parm(self, name: str, expression: str | None = None):
        parm = FakeParm(self, name, expression)
        self._parms[name] = parm
        return parm

    def parm(self, name: str):
        return self._parms.get(name)

    def parms(self):
        return list(self._parms.values())

    def add_child(self, name: str):
        child = FakeNode(f"{self._path}/{name}")
        self._children[name] = child
        return child

    def node(self, path: str):
        parts = [part for part in path.split("/") if part and part != "."]
        current = self
        for part in parts:
            if part == "..":
                current = getattr(current, "_parent", current)
                continue
            current = current._children.get(part)
            if current is None:
                return None
        return current

    def allSubChildren(self):
        rows = []
        for child in self._children.values():
            rows.append(child)
            rows.extend(child.allSubChildren())
        return rows


class FakeSession:
    def __init__(self, parms):
        self.hou = self
        self._parms = parms

    def parm(self, path):
        return self._parms.get(path)


class StructuralNode:
    def __init__(self, path: str, type_name: str, category: str = "Cop", children=None) -> None:
        self._path = path
        self._type_name = type_name
        self._category = category
        self._children = list(children or [])

    def path(self):
        return self._path

    def name(self):
        return self._path.rsplit("/", 1)[-1]

    def type(self):
        category = self._category
        type_name = self._type_name

        class _Type:
            def name(self):
                return type_name

            def category(self):
                return type("Category", (), {"name": lambda self: category})()

        return _Type()

    def children(self):
        return tuple(self._children)


class ConditionalTemplate:
    def __init__(self, rules):
        self._rules = rules

    def conditionals(self):
        return {
            type("ConditionalType", (), {"name": lambda self, name=name: name})(): value
            for name, value in self._rules.items()
        }


class ConditionalGroup:
    def __init__(self, templates):
        self._templates = templates

    def find(self, name):
        return self._templates.get(name)


def test_external_reference_audit_recurses_and_distinguishes_reference_kinds(monkeypatch) -> None:
    asset = FakeNode("/obj/geo1/asset1")
    internal = asset.add_child("internal_ctrl")
    internal._parent = asset
    internal.add_parm("inside_gain")
    probe = asset.add_child("probe")
    probe._parent = asset
    probe.add_parm("valid_relative", 'ch("../internal_ctrl/inside_gain")')
    probe.add_parm("valid_absolute", 'ch("/obj/geo1/asset1/internal_ctrl/inside_gain")')
    probe.add_parm("invalid_external", 'ch("/obj/geo1/outside/outside_gain")')
    probe.add_parm("missing_target", 'ch("/obj/geo1/missing/value")')
    external = FakeParm(FakeNode("/obj/geo1/outside"), "outside_gain")
    session = FakeSession(
        {
            "/obj/geo1/asset1/internal_ctrl/inside_gain": internal.parm("inside_gain"),
            "/obj/geo1/outside/outside_gain": external,
        }
    )
    monkeypatch.setattr(parm_refs, "localize", lambda value: value)

    result = parm_refs.external_reference_rows(session, asset)

    assert result["count"] == 1
    assert result["items"][0]["from_parm"] == "/obj/geo1/asset1/probe/invalid_external"
    assert result["items"][0]["to_parm"] == "/obj/geo1/outside/outside_gain"
    assert result["items"][0]["severity"] == "error"
    assert result["absolute_internal_count"] == 1
    assert result["absolute_internal"][0]["from_parm"] == "/obj/geo1/asset1/probe/valid_absolute"
    assert result["internal_count"] == 1
    assert result["reference_count"] == 3


def test_cop_output_audit_reports_noncanonical_output_nodes(monkeypatch) -> None:
    canonical = StructuralNode("/obj/cops/asset/outputs", "output")
    extra_a = StructuralNode("/obj/cops/asset/extra_a", "output")
    extra_b = StructuralNode("/obj/cops/asset/extra_b", "output")
    asset = StructuralNode(
        "/obj/cops/asset",
        "Scy::asset::1.0",
        children=[canonical, extra_a, extra_b],
    )
    monkeypatch.setattr(hda_validate, "localize", lambda value: value)

    result = hda_validate._cop_output_audit(asset)

    assert result is not None
    assert result["canonical"] == "/obj/cops/asset/outputs"
    assert result["extra_count"] == 2
    assert result["ok"] is False
    assert "extra_a" in result["warnings"][0]


def test_conditional_ui_audit_compares_definition_and_instance_templates(monkeypatch) -> None:
    rules = {"DisableWhen": "{ enabled == 0 }"}
    definition_group = ConditionalGroup({"amount": ConditionalTemplate(rules)})
    instance_group = ConditionalGroup({"amount": ConditionalTemplate(rules)})
    parm_tuple = type("ParmTuple", (), {"name": lambda self: "amount"})()
    parm = type("Parm", (), {"tuple": lambda self: parm_tuple})()
    node = type(
        "Asset",
        (),
        {
            "parms": lambda self: [parm],
            "parmTemplateGroup": lambda self: instance_group,
        },
    )()
    definition = type(
        "Definition",
        (),
        {"parmTemplateGroup": lambda self: definition_group},
    )()
    monkeypatch.setattr(hda_validate, "localize", lambda value: value)

    result = hda_validate._conditional_ui_audit(node, definition)

    assert result == {
        "count": 1,
        "items": [
            {
                "parm": "amount",
                "definition": rules,
                "instance": rules,
                "matches": True,
            }
        ],
        "mismatch_count": 0,
        "ok": True,
    }
