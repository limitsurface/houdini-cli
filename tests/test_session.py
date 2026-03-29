from argparse import Namespace

from houdini_cli.commands import session


class FakeHou:
    def __init__(self, frame=1.0) -> None:
        self._frame = frame
        self.hipFile = self

    def applicationVersionString(self):
        return "21.0.512"

    def path(self):
        return "C:/test.hip"

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
