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
