from types import SimpleNamespace

import pytest

from houdini_cli.commands import python_sop


def binding(**overrides):
    values = {"name": "", "type": "float", "ramptype": "float"}
    values.update(overrides)
    return values


def test_desired_python_sop_binding_rows_include_supported_controls() -> None:
    bindings = [
        binding(name="label", type="string"),
        binding(name="offset", type="float3"),
        binding(name="curve", type="ramp", ramptype="vector"),
        binding(name="P", type="attribute"),
    ]

    assert python_sop.desired_binding_rows(bindings) == [
        {"name": "label", "type": "string"},
        {"name": "offset", "type": "float3"},
        {"name": "curve", "type": "ramp"},
    ]


def test_require_python_sop_accepts_snippet(monkeypatch) -> None:
    parms = {"pythoncode": object(), "bindings": object()}
    node = SimpleNamespace(
        type=lambda: SimpleNamespace(
            name=lambda: "pythonsnippet",
            category=lambda: SimpleNamespace(name=lambda: "Sop"),
        ),
        parm=lambda name: parms.get(name),
        path=lambda: "/obj/geo1/snippet1",
    )
    monkeypatch.setattr(python_sop, "localize", lambda value: value)

    assert python_sop.require_python_sop(node) is parms["pythoncode"]


def test_require_python_sop_rejects_classic_python(monkeypatch) -> None:
    node = SimpleNamespace(
        type=lambda: SimpleNamespace(
            name=lambda: "python",
            category=lambda: SimpleNamespace(name=lambda: "Sop"),
        ),
        parm=lambda _name: None,
        path=lambda: "/obj/geo1/python1",
    )
    monkeypatch.setattr(python_sop, "localize", lambda value: value)

    with pytest.raises(ValueError, match="not a supported Python Snippet SOP"):
        python_sop.require_python_sop(node)
