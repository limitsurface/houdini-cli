from types import SimpleNamespace

import pytest

from houdini_cli.commands import hda_parms


class FakeTemplate:
    def __init__(self, kind, name, label=None, **kwargs):
        self.kind = kind
        self.name = name
        self.label = label
        self.kwargs = kwargs
        self.children = []
        self.callback = None
        self.callback_language = None

    def addParmTemplate(self, template):
        self.children.append(template)

    def setScriptCallback(self, callback):
        self.callback = callback

    def setScriptCallbackLanguage(self, language):
        self.callback_language = language

    def setHelp(self, value):
        self.kwargs["help"] = value

    def hide(self, value):
        self.kwargs["hidden"] = value

    def setJoinWithNext(self, value):
        self.kwargs["join_with_next"] = value


def _constructor(kind):
    return lambda name, label=None, *args, **kwargs: FakeTemplate(
        kind, name, label, args=args, **kwargs
    )


def fake_session():
    hou = SimpleNamespace(
        FloatParmTemplate=_constructor("float"),
        IntParmTemplate=_constructor("int"),
        ToggleParmTemplate=_constructor("toggle"),
        StringParmTemplate=_constructor("string"),
        MenuParmTemplate=_constructor("menu"),
        RampParmTemplate=_constructor("ramp"),
        FolderParmTemplate=_constructor("folder"),
        LabelParmTemplate=_constructor("heading"),
        SeparatorParmTemplate=lambda name: FakeTemplate("separator", name),
        scriptLanguage=SimpleNamespace(Python="Python", Hscript="Hscript"),
        folderType=SimpleNamespace(
            Tabs="Tabs",
            Simple="Simple",
            Collapsible="Collapsible",
            RadioButtons="RadioButtons",
        ),
        rampParmType=SimpleNamespace(Float="Float", Color="Color"),
        rampBasis=SimpleNamespace(
            Linear="Linear",
            Constant="Constant",
            CatmullRom="CatmullRom",
            MonotoneCubic="MonotoneCubic",
            Bezier="Bezier",
            BSpline="BSpline",
            Hermite="Hermite",
        ),
        colorType=SimpleNamespace(RGB="RGB", HSV="HSV", HSL="HSL", LAB="LAB", XYZ="XYZ"),
    )
    return SimpleNamespace(hou=hou)


def test_folder_schema_supports_nested_layout_templates() -> None:
    folder = hda_parms._folder_from_spec(
        fake_session(),
        {
            "type": "folder",
            "name": "composite",
            "label": "Composite",
            "folder_type": "tabs",
            "items": [
                {"type": "heading", "name": "signal_heading", "label": "Signal"},
                {"type": "separator", "name": "signal_separator"},
                {
                    "type": "folder",
                    "name": "noise",
                    "label": "Noise",
                    "folder_type": "collapsible",
                    "items": [{"type": "float", "name": "amount", "default": 0.5}],
                },
            ],
        },
    )

    assert folder.kwargs["folder_type"] == "Tabs"
    assert [child.kind for child in folder.children] == ["heading", "separator", "folder"]
    assert folder.children[2].kwargs["folder_type"] == "Collapsible"
    assert folder.children[2].children[0].name == "amount"


def test_parameter_schema_applies_python_callback() -> None:
    template = hda_parms._template_from_spec(
        fake_session(),
        {
            "type": "toggle",
            "name": "enabled",
            "callback": "hou.phm().update(kwargs)",
            "callback_language": "python",
        },
    )

    assert template.callback == "hou.phm().update(kwargs)"
    assert template.callback_language == "Python"


@pytest.mark.parametrize(
    ("kind", "expected_type", "extra"),
    [
        ("float_ramp", "Float", {"basis": "catmull_rom"}),
        ("color_ramp", "Color", {"basis": "linear", "color_space": "hsv"}),
    ],
)
def test_ramp_parameter_schema(kind, expected_type, extra) -> None:
    template = hda_parms._template_from_spec(
        fake_session(),
        {
            "type": kind,
            "name": "curve",
            "label": "Curve",
            "keys": 3,
            "show_controls": False,
            **extra,
        },
    )

    assert template.kind == "ramp"
    assert template.kwargs["args"][0] == expected_type
    assert template.kwargs["default_value"] == 3
    assert template.kwargs["show_controls"] is False
    if kind == "color_ramp":
        assert template.kwargs["color_type"] == "HSV"


def test_invalid_callback_language_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported callback language"):
        hda_parms._template_from_spec(
            fake_session(),
            {
                "type": "float",
                "name": "amount",
                "callback": "echo nope",
                "callback_language": "javascript",
            },
        )
