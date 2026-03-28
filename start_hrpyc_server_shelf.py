import hou

PORT = 18811

try:
    import hrpyc
except ImportError as exc:
    hou.ui.displayMessage(
        "Failed to import hrpyc.\n\n{}".format(exc),
        severity=hou.severityType.Error,
    )
    raise

try:
    hrpyc.start_server(port=PORT)
    message = "hrpyc server started on port {}".format(PORT)
except Exception as exc:
    text = str(exc).lower()
    if "in use" in text or "address already in use" in text:
        message = "Port {} is already in use. hrpyc may already be running.".format(PORT)
    else:
        hou.ui.displayMessage(
            "Failed to start hrpyc server on port {}.\n\n{}".format(PORT, exc),
            severity=hou.severityType.Error,
        )
        raise

hou.ui.displayMessage(message)
