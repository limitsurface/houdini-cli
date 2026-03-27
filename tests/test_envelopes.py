from houdini_cli.format.envelopes import error_result, success_result


def test_success_result_without_meta() -> None:
    assert success_result({"x": 1}) == {"ok": True, "data": {"x": 1}}


def test_success_result_with_meta() -> None:
    assert success_result({"x": 1}, {"truncated": False}) == {
        "ok": True,
        "data": {"x": 1},
        "meta": {"truncated": False},
    }


def test_error_result_contains_type_and_message() -> None:
    result = error_result(RuntimeError("bad"))
    assert result["ok"] is False
    assert result["error"]["type"].endswith("RuntimeError")
    assert result["error"]["message"] == "bad"
