import houdini_cli.runtime.timeouts as timeouts


def test_timeout_defaults_are_positive() -> None:
    assert timeouts.CONNECT_TIMEOUT_SECONDS > 0
    assert timeouts.SYNC_REQUEST_TIMEOUT_SECONDS > 0
