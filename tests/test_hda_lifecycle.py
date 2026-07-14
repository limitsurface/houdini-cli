from types import SimpleNamespace

from houdini_cli.commands import hda_lifecycle


class FakeDefinition:
    def __init__(self) -> None:
        self.min_inputs = None
        self.max_inputs = None
        self.icon = None
        self.parm_template_group = None

    def setMinNumInputs(self, value):
        self.min_inputs = value

    def setMaxNumInputs(self, value):
        self.max_inputs = value

    def setIcon(self, value):
        self.icon = value

    def setParmTemplateGroup(self, value):
        self.parm_template_group = value

    def sections(self):
        return {}

    def updateFromNode(self, node):
        self.updated_from = node


class FakeAsset:
    def __init__(self) -> None:
        self.definition = FakeDefinition()
        self.matched = False
        self.ptg = object()

    def type(self):
        return SimpleNamespace(category=lambda: SimpleNamespace(name=lambda: "Sop"))

    def parmTemplateGroup(self):
        return self.ptg

    def matchCurrentDefinition(self):
        self.matched = True


class FakeConnect:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self, _host, _port):
        return self

    def __enter__(self):
        return self.session

    def __exit__(self, _exc_type, _exc, _traceback):
        return False


def _package_args(**overrides):
    values = {
        "host": "localhost",
        "port": 18811,
        "subnet_path": "/obj/geo1/subnet1",
        "type_name": "Scy::test::1.0",
        "min_inputs": 1,
        "max_inputs": 1,
        "icon": None,
        "tab_submenu": None,
        "expanded_preview": False,
        "no_validate": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _patch_package_basics(monkeypatch, asset):
    monkeypatch.setattr(hda_lifecycle, "_create_asset_phase", lambda _args: asset.path)
    monkeypatch.setattr(hda_lifecycle, "_created_asset", lambda _session, _path, _type_name: asset)
    monkeypatch.setattr(hda_lifecycle, "definition_for_node", lambda _asset: asset.definition)
    monkeypatch.setattr(hda_lifecycle, "save_definition", lambda _definition: "test.hda")
    monkeypatch.setattr(hda_lifecycle, "node_summary", lambda _asset: {"path": asset.path})
    monkeypatch.setattr(
        hda_lifecycle,
        "definition_summary",
        lambda _session, _definition: {"type": "Scy::test::1.0"},
    )
    monkeypatch.setattr(hda_lifecycle, "connect", FakeConnect(SimpleNamespace(hou=SimpleNamespace())))


def test_handle_package_reports_validation_failure_without_raising(monkeypatch) -> None:
    asset = FakeAsset()
    asset.path = "/obj/geo1/subnet1"
    _patch_package_basics(monkeypatch, asset)

    def broken_validation(_session, _asset, **_kwargs):
        raise RuntimeError("cook failed")

    monkeypatch.setattr(hda_lifecycle, "validate_asset", broken_validation)

    result = hda_lifecycle.handle_package(_package_args())

    assert result["ok"] is True
    assert result["data"]["node"] == {"path": "/obj/geo1/subnet1"}
    assert result["data"]["validation"]["ok"] is False
    assert result["data"]["validation"]["error"]["message"] == "cook failed"
    assert asset.definition.parm_template_group is asset.ptg
    assert asset.matched is True


def test_handle_package_no_validate_skips_validation(monkeypatch) -> None:
    asset = FakeAsset()
    asset.path = "/obj/geo1/subnet1"
    _patch_package_basics(monkeypatch, asset)

    def unexpected_validation(_session, _asset, **_kwargs):
        raise AssertionError("validation should not run")

    monkeypatch.setattr(hda_lifecycle, "validate_asset", unexpected_validation)

    result = hda_lifecycle.handle_package(_package_args(no_validate=True))

    assert result["ok"] is True
    assert result["data"]["validation"] is None
    assert asset.definition.parm_template_group is asset.ptg


def test_handle_create_copies_source_interface(monkeypatch) -> None:
    asset = FakeAsset()
    asset.path = "/obj/geo1/subnet1"
    _patch_package_basics(monkeypatch, asset)

    result = hda_lifecycle.handle_create(_package_args())

    assert result["ok"] is True
    assert asset.definition.parm_template_group is asset.ptg


def _update_args(**overrides):
    values = {
        "host": "localhost",
        "port": 18811,
        "asset_node": "/obj/geo1/asset1",
        "contents": True,
        "interface": False,
        "sections": False,
        "tools": False,
        "all": False,
        "no_save": False,
        "no_match": False,
        "validate": True,
        "validate_cook": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _patch_update_basics(monkeypatch, asset):
    monkeypatch.setattr(
        hda_lifecycle,
        "connect",
        FakeConnect(SimpleNamespace(hou=SimpleNamespace())),
    )
    monkeypatch.setattr(hda_lifecycle, "get_node", lambda _session, _path: asset)
    monkeypatch.setattr(hda_lifecycle, "definition_for_node", lambda _asset: asset.definition)
    monkeypatch.setattr(hda_lifecycle, "save_definition", lambda _definition: "test.hda")


def test_handle_update_validate_does_not_force_cook(monkeypatch) -> None:
    asset = FakeAsset()
    _patch_update_basics(monkeypatch, asset)
    calls = []

    def fake_validation(_session, _asset, **kwargs):
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(hda_lifecycle, "validate_asset", fake_validation)

    result = hda_lifecycle.handle_update(_update_args())

    assert result["ok"] is True
    assert calls == [{"fresh": True, "cook": False, "frames": []}]
    assert asset.matched is True


def test_handle_update_validate_cook_is_explicit(monkeypatch) -> None:
    asset = FakeAsset()
    _patch_update_basics(monkeypatch, asset)
    calls = []

    def fake_validation(_session, _asset, **kwargs):
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(hda_lifecycle, "validate_asset", fake_validation)

    result = hda_lifecycle.handle_update(
        _update_args(validate=False, validate_cook=True)
    )

    assert result["ok"] is True
    assert calls == [{"fresh": True, "cook": True, "frames": []}]


def test_handle_update_reports_validation_failure_after_saving(monkeypatch) -> None:
    asset = FakeAsset()
    _patch_update_basics(monkeypatch, asset)
    monkeypatch.setattr(
        hda_lifecycle,
        "validate_asset",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("cook failed")),
    )

    result = hda_lifecycle.handle_update(_update_args())

    assert result["ok"] is True
    assert result["data"]["library"] == "test.hda"
    assert result["data"]["validation"]["ok"] is False
    assert result["data"]["validation"]["error"]["message"] == "cook failed"
