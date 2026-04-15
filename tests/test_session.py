import os
from argparse import Namespace
from types import SimpleNamespace

import pytest

from houdini_cli.commands import session


class FakeHou:
    def __init__(self, frame=1.0, selected_nodes=()) -> None:
        self._frame = frame
        self._selected_nodes = tuple(selected_nodes)
        self.hipFile = self
        self.paneTabType = SimpleNamespace(SceneViewer="SceneViewer")
        self.geometryViewportType = SimpleNamespace(
            Perspective="Perspective",
            Top="Top",
            Bottom="Bottom",
            Front="Front",
            Back="Back",
            Right="Right",
            Left="Left",
        )
        self.hmath = SimpleNamespace(buildRotate=lambda rotates: FakeRotateBuilder(rotates))
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

    def selectedNodes(self, include_hidden=False):
        return self._selected_nodes


class FakeNode:
    def __init__(self, path) -> None:
        self._path = path

    def path(self):
        return self._path


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
    def __init__(self, name, pane_type, current=False, viewport=None) -> None:
        self._name = name
        self._type = pane_type
        self._current = current
        self._viewport = viewport or FakeViewport()

    def name(self):
        return self._name

    def type(self):
        return self._type

    def curViewport(self):
        return self._viewport


class FakeRotationMatrix:
    def __init__(self, rotates) -> None:
        self._rotates = tuple(rotates)

    def extractRotates(self):
        return self._rotates


class FakeRotateBuilder:
    def __init__(self, rotates) -> None:
        self._matrix = FakeRotationMatrix(rotates)

    def extractRotationMatrix3(self):
        return self._matrix


class FakeCamera:
    def __init__(self, perspective=True, translation=(0.0, 0.0, 5.0), pivot=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0)) -> None:
        self._perspective = perspective
        self._translation = tuple(translation)
        self._pivot = tuple(pivot)
        self._rotation = tuple(rotation)

    def isPerspective(self):
        return self._perspective

    def translation(self):
        return self._translation

    def pivot(self):
        return self._pivot

    def rotation(self):
        return FakeRotationMatrix(self._rotation)

    def setTranslation(self, xyz):
        self._translation = tuple(xyz)

    def setPivot(self, xyz):
        self._pivot = tuple(xyz)

    def setRotation(self, matrix):
        self._rotation = tuple(matrix.extractRotates())


class FakeViewport:
    def __init__(self, name="persp1", viewport_type="Perspective", camera=None) -> None:
        self._name = name
        self._type = viewport_type
        self._camera = camera or FakeCamera(perspective=viewport_type == "Perspective")
        self.frame_selected_calls = 0
        self.draw_calls = 0

    def name(self):
        return self._name

    def type(self):
        return self._type

    def defaultCamera(self):
        return self._camera

    def frameSelected(self):
        self.frame_selected_calls += 1
        self._camera.setTranslation((2.0, 3.5, 5.3))
        self._camera.setPivot((2.0, 3.5, 4.0))

    def draw(self):
        self.draw_calls += 1

    def changeType(self, viewport_type):
        self._type = viewport_type
        self._camera._perspective = viewport_type == "Perspective"


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


def test_handle_selection_reads_selected_nodes(monkeypatch) -> None:
    fake_hou = FakeHou(selected_nodes=(FakeNode("/obj/geo1/box1"), FakeNode("/obj/geo1/null1")))
    monkeypatch.setattr(session, "connect", FakeConnect(FakeSession(fake_hou)))
    monkeypatch.setattr(session, "localize", lambda value: value)

    result = session.handle_selection(
        Namespace(host="localhost", port=18811, include_hidden=False)
    )

    assert result == {
        "ok": True,
        "data": {
            "count": 2,
            "paths": ["/obj/geo1/box1", "/obj/geo1/null1"],
            "current": "/obj/geo1/null1",
            "include_hidden": False,
        },
    }


def test_handle_screenshot_uses_single_scene_viewer(monkeypatch) -> None:
    fake_hou = FakeHou()
    pane = FakePane("panetab1", fake_hou.paneTabType.SceneViewer, current=True)
    fake_hou.ui = FakeUI([pane])
    fake_session = FakeSession(fake_hou)
    expected_path = os.path.join("C:/houdini_cli", "screenshots", "viewport_panetab1_20260331_140000.png")
    fake_session.connection.modules.os.files[expected_path] = 123

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
    assert result["data"]["path"] == expected_path
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


def test_handle_viewport_get_reads_viewport_state(monkeypatch) -> None:
    fake_hou = FakeHou()
    viewport = FakeViewport(camera=FakeCamera(translation=(1.0, 2.0, 3.0), pivot=(4.0, 5.0, 6.0), rotation=(7.0, 8.0, 9.0)))
    pane = FakePane("panetab1", fake_hou.paneTabType.SceneViewer, current=True, viewport=viewport)
    fake_hou.ui = FakeUI([pane])
    monkeypatch.setattr(session, "connect", FakeConnect(FakeSession(fake_hou)))
    monkeypatch.setattr(session, "localize", lambda value: value)

    result = session.handle_viewport_get(
        Namespace(host="localhost", port=18811, pane_name=None, index=None)
    )

    assert result == {
        "ok": True,
        "data": {
            "pane_name": "panetab1",
            "viewport_name": "persp1",
            "viewport_type": "Perspective",
            "is_perspective": True,
            "translation": [1.0, 2.0, 3.0],
            "pivot": [4.0, 5.0, 6.0],
            "rotation": [7.0, 8.0, 9.0],
        },
    }


def test_handle_viewport_focus_selected_frames_selection(monkeypatch) -> None:
    fake_hou = FakeHou()
    viewport = FakeViewport()
    pane = FakePane("panetab1", fake_hou.paneTabType.SceneViewer, current=True, viewport=viewport)
    fake_hou.ui = FakeUI([pane])
    monkeypatch.setattr(session, "connect", FakeConnect(FakeSession(fake_hou)))
    monkeypatch.setattr(session, "localize", lambda value: value)

    result = session.handle_viewport_focus_selected(
        Namespace(host="localhost", port=18811, pane_name=None, index=None)
    )

    assert result["ok"] is True
    assert result["data"]["action"] == "focus-selected"
    assert result["data"]["translation"] == [2.0, 3.5, 5.3]
    assert viewport.frame_selected_calls == 1
    assert viewport.draw_calls == 1


def test_handle_viewport_axis_changes_view_type(monkeypatch) -> None:
    fake_hou = FakeHou()
    viewport = FakeViewport()
    pane = FakePane("panetab1", fake_hou.paneTabType.SceneViewer, current=True, viewport=viewport)
    fake_hou.ui = FakeUI([pane])
    monkeypatch.setattr(session, "connect", FakeConnect(FakeSession(fake_hou)))
    monkeypatch.setattr(session, "localize", lambda value: value)

    result = session.handle_viewport_axis(
        Namespace(host="localhost", port=18811, pane_name=None, index=None, axis="+x")
    )

    assert result["ok"] is True
    assert result["data"]["axis"] == "+x"
    assert result["data"]["viewport_type"] == "Right"
    assert result["data"]["is_perspective"] is False


def test_handle_viewport_set_updates_perspective_camera(monkeypatch) -> None:
    fake_hou = FakeHou()
    viewport = FakeViewport()
    pane = FakePane("panetab1", fake_hou.paneTabType.SceneViewer, current=True, viewport=viewport)
    fake_hou.ui = FakeUI([pane])
    monkeypatch.setattr(session, "connect", FakeConnect(FakeSession(fake_hou)))
    monkeypatch.setattr(session, "localize", lambda value: value)

    result = session.handle_viewport_set(
        Namespace(
            host="localhost",
            port=18811,
            pane_name=None,
            index=None,
            t=[10.0, 20.0, 30.0],
            r=[15.0, 25.0, 35.0],
            pivot=[1.0, 2.0, 3.0],
        )
    )

    assert result["ok"] is True
    assert result["data"]["action"] == "set"
    assert result["data"]["translation"] == [10.0, 20.0, 30.0]
    assert result["data"]["pivot"] == [1.0, 2.0, 3.0]
    assert result["data"]["rotation"] == [15.0, 25.0, 35.0]


def test_handle_viewport_set_rejects_non_perspective_view(monkeypatch) -> None:
    fake_hou = FakeHou()
    viewport = FakeViewport(viewport_type="Top", camera=FakeCamera(perspective=False))
    pane = FakePane("panetab1", fake_hou.paneTabType.SceneViewer, current=True, viewport=viewport)
    fake_hou.ui = FakeUI([pane])
    monkeypatch.setattr(session, "connect", FakeConnect(FakeSession(fake_hou)))
    monkeypatch.setattr(session, "localize", lambda value: value)

    with pytest.raises(ValueError, match="only supports perspective views"):
        session.handle_viewport_set(
            Namespace(
                host="localhost",
                port=18811,
                pane_name=None,
                index=None,
                t=[1.0, 2.0, 3.0],
                r=None,
                pivot=None,
            )
        )
