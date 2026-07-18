import hou
import threading

PORT_OPTIONS = (
    ("Default port (18811)", 18811),
    ("Port 18812", 18812),
    ("Port 18813", 18813),
    ("Port 18814", 18814),
)

selection = hou.ui.displayMessage(
    (
        "Choose the port for this Houdini instance.\n\n"
        "When using a non-default port, inform the agent so it can pass "
        "--port <port> before the CLI command."
    ),
    buttons=tuple(label for label, _port in PORT_OPTIONS),
    default_choice=0,
    close_choice=-1,
    title="Start Houdini CLI Server",
)

if selection < 0:
    raise SystemExit

PORT = PORT_OPTIONS[selection][1]

try:
    import hrpyc
except ImportError as exc:
    hou.ui.displayMessage(
        "Failed to import hrpyc.\n\n{}".format(exc),
        severity=hou.severityType.Error,
    )
    raise

current_server = getattr(hou.session, "_houdini_cli_server", None)
current_thread = getattr(hou.session, "_houdini_cli_server_thread", None)
current_port = getattr(hou.session, "_houdini_cli_server_port", None)
server_active = False

if current_server is not None and current_port == PORT:
    message = "hrpyc server is already running on port {}.".format(PORT)
    server_active = True
else:
    try:
        # ThreadedServer binds its listener during construction. Build the new
        # server before closing the old one so a busy destination port does not
        # interrupt the working connection.
        new_server = hrpyc.ThreadedServer(
            hrpyc.SlaveService,
            hostname="0.0.0.0",
            port=PORT,
            reuse_addr=True,
            registrar=None,
            auto_register=False,
        )
        new_server.logger.quiet = True
    except Exception as exc:
        text = str(exc).lower()
        if "in use" in text or "address already in use" in text:
            message = "Port {} is already in use. Choose another port.".format(PORT)
        else:
            hou.ui.displayMessage(
                "Failed to prepare hrpyc server on port {}.\n\n{}".format(PORT, exc),
                severity=hou.severityType.Error,
            )
            raise
    else:
        if current_server is not None:
            current_server.close()
            if current_thread is not None and current_thread.is_alive():
                current_thread.join(2.0)

        new_thread = threading.Thread(
            target=new_server.start,
            name="houdini-cli-{}".format(PORT),
        )
        new_thread.start()
        hou.session._houdini_cli_server = new_server
        hou.session._houdini_cli_server_thread = new_thread
        hou.session._houdini_cli_server_port = PORT
        server_active = True

        if current_port is None:
            message = "hrpyc server started on port {}.".format(PORT)
        else:
            message = "hrpyc server switched from port {} to {}.".format(current_port, PORT)

if server_active and PORT != 18811:
    message += "\n\nTell the agent to use --port {} before each CLI command.".format(PORT)

hou.ui.displayMessage(message)
