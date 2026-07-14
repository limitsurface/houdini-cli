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


class FlatTemplate:
    def __init__(self, name, label, type_name, children=None, default=None):
        self._name = name
        self._label = label
        self._type_name = type_name
        self._children = children
        self._default = default

    def name(self):
        return self._name

    def label(self):
        return self._label

    def type(self):
        return SimpleNamespace(name=lambda: self._type_name)

    def parmTemplates(self):
        return self._children or []

    def defaultValue(self):
        return self._default


class FlatParm:
    def __init__(self, value):
        self._value = value

    def eval(self):
        return self._value


class FlatNode:
    def parm(self, name):
        values = {"processing_scale": 0.75, "filter_type": 1}
        return FlatParm(values[name]) if name in values else None


def test_flat_parm_rows_preserve_names_and_folder_paths() -> None:
    entries = [
        FlatTemplate(
            "general",
            "General",
            "Folder",
            [
                FlatTemplate("processing_scale", "Processing Scale", "Float", default=(1.0,)),
                FlatTemplate("filter_type", "Low-Pass Filter Type", "Menu", default=1),
            ],
        )
    ]

    rows = hda_parms._flat_parm_rows(
        FlatNode(),
        entries,
        include_values=True,
        include_defaults=True,
    )

    assert rows == [
        ["processing_scale", "Processing Scale", "Float", "General", 0.75, (1.0,)],
        ["filter_type", "Low-Pass Filter Type", "Menu", "General", 1, 1],
    ]


def test_flat_parm_rows_filter_by_folder_and_name() -> None:
    entries = [
        FlatTemplate(
            "vhs",
            "VHS FX",
            "Folder",
            [FlatTemplate("filter_type", "Low-Pass Filter Type", "Menu", default=1)],
        )
    ]

    assert hda_parms._flat_parm_rows(
        FlatNode(), entries, folder_filter="vhs", name_filter="filter"
    ) == [["filter_type", "Low-Pass Filter Type", "Menu", "VHS FX"]]


class FakeConnect:
    def __init__(self, session):
        self.session = session

    def __call__(self, _host, _port):
        return self

    def __enter__(self):
        return self.session

    def __exit__(self, _exc_type, _exc, _traceback):
        return False


def test_defaults_folder_updates_only_matching_parameter_names(monkeypatch) -> None:
    session = SimpleNamespace()
    captured = {}
    monkeypatch.setattr(hda_parms, "connect", FakeConnect(session))
    monkeypatch.setattr(
        hda_parms,
        "_flat_parm_rows_in_houdini",
        lambda _session, _path, **kwargs: [
            ["noise_enable", "Enable", "Toggle", "Composite/Noise & Defects"],
            ["snow_intensity", "Intensity", "Float", "Composite/Noise & Defects"],
        ],
    )

    def fake_update(_session, node_path, *, names):
        captured["node_path"] = node_path
        captured["names"] = names
        return {"updated_defaults": len(names), "library": "test.hda"}

    monkeypatch.setattr(hda_parms, "_set_defaults_from_current_in_houdini", fake_update)
    args = SimpleNamespace(
        host="localhost",
        port=18811,
        asset_node="/obj/composite1",
        from_current=True,
        folder="Noise & Defects",
    )

    result = hda_parms.handle_parms_defaults(args)

    assert result["ok"] is True
    assert result["data"]["updated_defaults"] == 2
    assert result["data"]["folder"] == "Noise & Defects"
    assert captured == {
        "node_path": "/obj/composite1",
        "names": ["noise_enable", "snow_intensity"],
    }
