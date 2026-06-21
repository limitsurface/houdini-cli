from types import SimpleNamespace

from houdini_cli.commands import hda_inspect


def _definition(type_name: str) -> SimpleNamespace:
    return SimpleNamespace(type_name=type_name)


def _summary(definition: SimpleNamespace) -> dict:
    name = definition.type_name.split("::")[-2]
    return {
        "type_name": definition.type_name,
        "components": {
            "scope": "",
            "namespace": "Scy",
            "name": name,
            "version": "1.0",
        },
        "label": name,
        "category": "Cop",
        "library": "C:/otls/test.hda",
        "version": "1.0",
        "icon": "",
        "min_inputs": 0,
        "max_inputs": 1,
        "preferred": False,
        "current": True,
        "sections": [{"name": "Tools.shelf", "size": 123}],
    }


def test_definition_rows_are_capped_before_broad_results(monkeypatch) -> None:
    monkeypatch.setattr(
        hda_inspect,
        "_all_definitions",
        lambda session: [
            _definition("Scy::ntsc_hou::1.0"),
            _definition("Scy::ntsc_vhs::1.0"),
            _definition("Scy::ntsc_composite::1.0"),
        ],
    )
    monkeypatch.setattr(hda_inspect, "definition_summary", lambda session, definition: _summary(definition))
    args = SimpleNamespace(
        library=None,
        category=None,
        namespace="Scy",
        name=None,
        type_name=None,
        sections=False,
        max=2,
        all=False,
    )

    result = hda_inspect._definition_rows_in_houdini(SimpleNamespace(), args)

    assert result["count"] == 2
    assert result["total_matches"] == 3
    assert result["truncated"] is True
    assert result["limit"] == 2
    assert "sections" not in result["definitions"][0]


def test_definition_rows_can_include_sections(monkeypatch) -> None:
    monkeypatch.setattr(hda_inspect, "_all_definitions", lambda session: [_definition("Scy::ntsc_hou::1.0")])
    monkeypatch.setattr(hda_inspect, "definition_summary", lambda session, definition: _summary(definition))
    args = SimpleNamespace(
        library=None,
        category=None,
        namespace=None,
        name=None,
        type_name=None,
        sections=True,
        max=50,
        all=False,
    )

    result = hda_inspect._definition_rows_in_houdini(SimpleNamespace(), args)

    assert result["definitions"][0]["sections"] == [{"name": "Tools.shelf", "size": 123}]
