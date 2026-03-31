from argparse import Namespace

from houdini_cli.commands import eval as eval_command


class FakeConnection:
    def __init__(self) -> None:
        self.namespace = {}
        self.executed = []

    def execute(self, code):
        self.executed.append(code)
        source = self.namespace["_houdini_cli_eval_code"]
        stdout = []
        stderr = []

        def fake_print(*args, **kwargs):
            stdout.append(" ".join(str(arg) for arg in args))

        remote_globals = {
            "__builtins__": __builtins__,
            "hou": FakeHou(),
            "print": fake_print,
            "emit_stderr": lambda text: stderr.append(text),
        }
        exec(source, remote_globals)
        self.namespace["_houdini_cli_eval_stdout"] = "" if not stdout else "\n".join(stdout) + "\n"
        self.namespace["_houdini_cli_eval_stderr"] = "" if not stderr else "".join(stderr)


class FakeHou:
    def applicationVersionString(self):
        return "21.0.512"


class FakeSession:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.hou = FakeHou()


class FakeConnect:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self, host, port):
        class _Ctx:
            def __enter__(inner_self):
                return self.session

            def __exit__(inner_self, exc_type, exc, tb):
                return False

        return _Ctx()


class FakeTimeout:
    def __init__(self):
        self.calls = []

    def __call__(self, session, seconds):
        self.calls.append((session, seconds))

        class _Ctx:
            def __enter__(inner_self):
                return None

            def __exit__(inner_self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_handle_eval_executes_in_remote_session(monkeypatch) -> None:
    session = FakeSession()
    fake_timeout = FakeTimeout()
    monkeypatch.setattr(eval_command, "connect", FakeConnect(session))
    monkeypatch.setattr(eval_command, "sync_request_timeout", fake_timeout)
    monkeypatch.setattr(eval_command, "localize", lambda value: value)

    result = eval_command.handle_eval(
        Namespace(
            host="localhost",
            port=18811,
            code="import math\nprint(hou.applicationVersionString())\nprint(math.sqrt(9))",
        )
    )

    assert result["ok"] is True
    assert result["data"]["stdout"] == "21.0.512\n3.0\n"
    assert result["data"]["stderr"] == ""
    assert session.connection.executed


def test_handle_eval_captures_stderr(monkeypatch) -> None:
    session = FakeSession()
    fake_timeout = FakeTimeout()
    monkeypatch.setattr(eval_command, "connect", FakeConnect(session))
    monkeypatch.setattr(eval_command, "sync_request_timeout", fake_timeout)
    monkeypatch.setattr(eval_command, "localize", lambda value: value)

    result = eval_command.handle_eval(
        Namespace(
            host="localhost",
            port=18811,
            code="emit_stderr('problem\\n')",
        )
    )

    assert result["ok"] is True
    assert result["data"]["stdout"] == ""
    assert result["data"]["stderr"] == "problem\n"
