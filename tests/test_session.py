from argparse import Namespace
from types import SimpleNamespace

import pytest

from houdini_cli.commands import session


class FakeHou:
    def __init__(self, frame=1.0) -> None:
        self._frame = frame
        self.hipFile = self
        self.paneTabType = SimpleNamespace(SceneViewer="SceneViewer")
        self.ui = FakeUI([])

    def applicationVersionString(self):
        return "21.0.512"

    def path(self):
        return "C:/test.hip"

    def isUIAvailable(self):
        return True

    def expandString(self, value):
        return value.replace("$HIP", "C:/test")

    def setFrame(self, frame):
        self._frame = frame

    def frame(self):
        return self._frame

    def hscript(self, command):
        if command.startswith("fcur "):
            self._frame = int(command.split(" ", 1)[1])
            return ("", "")
        if command == "fcur":
            return (f"Frame {int(self._frame)} ({(self._frame - 1) / 24.0} sec.)", "")
        raise AssertionError(f"Unexpected hscript command: {command}")


class FakeSession:
    def __init__(self, hou_obj: FakeHou) -> None:
        self.hou = hou_obj
        self.connection = SimpleNamespace(
            modules=SimpleNamespace(
                os=FakeOsModule(),
                tempfile=SimpleNamespace(gettempdir=lambda: "C:/temp"),
                husd=SimpleNamespace(assetutils=FakeAssetUtils()),
            )
        )


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


class FakePane:
    def __init__(self, name, pane_type, current=False) -> None:
        self._name = name
        self._type = pane_type
        self._current = current

    def name(self):
        return self._name

    def type(self):
        return self._type


class FakeDesktop:
    def __init__(self, panes) -> None:
        self._panes = list(panes)

    def paneTabs(self):
        return tuple(self._panes)

    def currentPaneTabs(self):
        return tuple(pane for pane in self._panes if getattr(pane, "_current", False))


class FakeUI:
    def __init__(self, panes) -> None:
        self._desktop = FakeDesktop(panes)

    def curDesktop(self):
        return self._desktop


class FakeOsModule:
    def __init__(self) -> None:
        self.created = []
        self.files = {}
        self.path = self

    def makedirs(self, path, exist_ok=False):
        self.created.append((path, exist_ok))

    def exists(self, path):
        return path in self.files

    def getsize(self, path):
        return self.files[path]

    @staticmethod
    def abspath(value):
        return value

    @staticmethod
    def dirname(value):
        return value.rsplit("/", 1)[0] if "/" in value else ""


class FakeAssetUtils:
    def __init__(self) -> None:
        self.calls = []

    def saveThumbnailFromViewer(self, sceneviewer=None, output="", frame=None, res=(256, 256), croptocamera=True):
        self.calls.append(
            {
                "sceneviewer": sceneviewer,
                "output": output,
                "frame": frame,
                "res": res,
                "croptocamera": croptocamera,
            }
        )


def test_handle_frame_reads_current_frame(monkeypatch) -> None:
    monkeypatch.setattr(session, "connect", FakeConnect(FakeSession(FakeHou(frame=12))))
    monkeypatch.setattr(session, "localize", lambda value: value)

    result = session.handle_frame(Namespace(host="localhost", port=18811, frame=None))

    assert result == {"ok": True, "data": {"frame": 12}}


def test_handle_frame_sets_current_frame(monkeypatch) -> None:
    fake_hou = FakeHou(frame=1.0)
    monkeypatch.setattr(session, "connect", FakeConnect(FakeSession(fake_hou)))
    monkeypatch.setattr(session, "localize", lambda value: value)

    result = session.handle_frame(Namespace(host="localhost", port=18811, frame=24))

    assert fake_hou.frame() == 24
    assert result == {"ok": True, "data": {"frame": 24}}


def test_handle_screenshot_uses_single_scene_viewer(monkeypatch) -> None:
    fake_hou = FakeHou()
    pane = FakePane("panetab1", fake_hou.paneTabType.SceneViewer, current=True)
    fake_hou.ui = FakeUI([pane])
    fake_session = FakeSession(fake_hou)
    fake_session.connection.modules.os.files[r"C:/houdini_cli\screenshots\viewport_panetab1_20260331_140000.png"] = 123

    monkeypatch.setattr(session, "connect", FakeConnect(fake_session))
    monkeypatch.setattr(session, "localize", lambda value: value)
    monkeypatch.setattr(session, "datetime", SimpleNamespace(now=lambda: SimpleNamespace(strftime=lambda fmt: "20260331_140000")))

    result = session.handle_screenshot(
        Namespace(
            host="localhost",
            port=18811,
            pane_name=None,
            index=None,
            output=None,
            frame=1,
            width=512,
            height=512,
        )
    )

    assert result["ok"] is True
    assert result["data"]["pane_name"] == "panetab1"
    assert result["data"]["path"] == r"C:/houdini_cli\screenshots\viewport_panetab1_20260331_140000.png"
    assert fake_session.connection.modules.husd.assetutils.calls[0]["sceneviewer"] is pane


def test_handle_screenshot_requires_disambiguation_with_multiple_current_viewers(monkeypatch) -> None:
    fake_hou = FakeHou()
    panes = [
        FakePane("panetab1", fake_hou.paneTabType.SceneViewer, current=True),
        FakePane("panetab15", fake_hou.paneTabType.SceneViewer, current=True),
    ]
    fake_hou.ui = FakeUI(panes)

    monkeypatch.setattr(session, "connect", FakeConnect(FakeSession(fake_hou)))
    monkeypatch.setattr(session, "localize", lambda value: value)

    with pytest.raises(ValueError, match="Multiple Scene Viewers"):
        session.handle_screenshot(
            Namespace(
                host="localhost",
                port=18811,
                pane_name=None,
                index=None,
                output=None,
                frame=1,
                width=512,
                height=512,
            )
        )


def test_handle_screenshot_uses_explicit_pane_name(monkeypatch) -> None:
    fake_hou = FakeHou()
    panes = [
        FakePane("panetab1", fake_hou.paneTabType.SceneViewer, current=True),
        FakePane("panetab15", fake_hou.paneTabType.SceneViewer, current=True),
    ]
    fake_hou.ui = FakeUI(panes)
    fake_session = FakeSession(fake_hou)
    fake_session.connection.modules.os.files["D:/out.png"] = 456

    monkeypatch.setattr(session, "connect", FakeConnect(fake_session))
    monkeypatch.setattr(session, "localize", lambda value: value)

    result = session.handle_screenshot(
        Namespace(
            host="localhost",
            port=18811,
            pane_name="panetab15",
            index=None,
            output="D:/out.png",
            frame=2,
            width=256,
            height=128,
        )
    )

    assert result["ok"] is True
    assert result["data"]["pane_name"] == "panetab15"
    call = fake_session.connection.modules.husd.assetutils.calls[0]
    assert call["sceneviewer"] is panes[1]
    assert call["res"] == (256, 128)
    assert call["frame"] == 2
