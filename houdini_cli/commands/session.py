"""Session-oriented commands."""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize

_FCUR_FRAME_PATTERN = re.compile(r"Frame\s+(-?\d+(?:\.\d+)?)")


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ping_parser = subparsers.add_parser("ping", help="Verify Houdini connectivity.")
    ping_parser.set_defaults(handler=handle_ping)

    session_parser = subparsers.add_parser("session", help="Inspect or control the live Houdini session.")
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)

    session_ping_parser = session_subparsers.add_parser("ping", help="Verify Houdini connectivity.")
    session_ping_parser.set_defaults(handler=handle_ping)

    frame_parser = session_subparsers.add_parser(
        "frame",
        help="Get or set the current timeline frame.",
    )
    frame_parser.add_argument("frame", nargs="?", type=int, help="Optional frame to set before reporting.")
    frame_parser.set_defaults(handler=handle_frame)

    screenshot_parser = session_subparsers.add_parser(
        "screenshot",
        help="Capture a screenshot from a Scene Viewer pane.",
    )
    screenshot_parser.add_argument(
        "--pane-name",
        help="Scene Viewer pane name, for example panetab1.",
    )
    screenshot_parser.add_argument(
        "--index",
        type=int,
        help="Scene Viewer index from the current desktop ordering.",
    )
    screenshot_parser.add_argument(
        "--output",
        help="Optional output path. Defaults to $HIP/houdini_cli/screenshots/<timestamp>.png",
    )
    screenshot_parser.add_argument(
        "--frame",
        type=int,
        default=1,
        help="Frame to capture (default: 1).",
    )
    screenshot_parser.add_argument(
        "--width",
        type=int,
        default=512,
        help="Output width in pixels (default: 512).",
    )
    screenshot_parser.add_argument(
        "--height",
        type=int,
        default=512,
        help="Output height in pixels (default: 512).",
    )
    screenshot_parser.set_defaults(handler=handle_screenshot)


def handle_ping(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        return success_result(
            {
                "host": args.host,
                "port": args.port,
                "houdini_version": localize(session.hou.applicationVersionString()),
                "hip_file": localize(session.hou.hipFile.path()),
            }
        )


def handle_frame(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        requested_frame = getattr(args, "frame", None)
        if requested_frame is not None:
            session.hou.hscript(f"fcur {requested_frame}")

        output, _ = session.hou.hscript("fcur")
        current_frame = _parse_fcur_frame(localize(output))

        return success_result(
            {
                "frame": current_frame,
            }
        )


def _parse_fcur_frame(output: str) -> int:
    match = _FCUR_FRAME_PATTERN.search(output)
    if not match:
        raise ValueError(f"Unexpected fcur output: {output!r}")
    return int(float(match.group(1)))


def _scene_viewers(session) -> list:
    desktop = session.hou.ui.curDesktop()
    return [tab for tab in desktop.paneTabs() if tab.type() == session.hou.paneTabType.SceneViewer]


def _resolve_scene_viewer(session, *, pane_name: str | None, index: int | None):
    if pane_name and index is not None:
        raise ValueError("Use only one of --pane-name or --index")
    if not session.hou.isUIAvailable():
        raise ValueError("Houdini UI is not available")

    viewers = _scene_viewers(session)
    if not viewers:
        raise ValueError("No Scene Viewer pane is available")

    if pane_name:
        for viewer in viewers:
            if localize(viewer.name()) == pane_name:
                return viewer
        raise ValueError(f"Scene Viewer not found: {pane_name}")

    if index is not None:
        if index < 0 or index >= len(viewers):
            raise ValueError(f"Scene Viewer index out of range: {index}")
        return viewers[index]

    current_viewers = [
        tab
        for tab in session.hou.ui.curDesktop().currentPaneTabs()
        if tab.type() == session.hou.paneTabType.SceneViewer
    ]
    if len(current_viewers) == 1:
        return current_viewers[0]
    if len(viewers) == 1:
        return viewers[0]
    raise ValueError("Multiple Scene Viewers are available; use --pane-name or --index")


def _default_screenshot_path(session, pane_name: str) -> str:
    hip_path = localize(session.hou.hipFile.path())
    hip_dir = os.path.dirname(hip_path) if hip_path else ""
    if not hip_dir:
        hip_dir = localize(session.connection.modules.tempfile.gettempdir())
    folder = os.path.join(hip_dir, "houdini_cli", "screenshots")
    session.connection.modules.os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(folder, f"viewport_{pane_name}_{timestamp}.png")


def _resolve_output_path(session, output: str | None, pane_name: str) -> str:
    if not output:
        return _default_screenshot_path(session, pane_name)
    expanded = localize(session.hou.expandString(output))
    resolved = localize(session.connection.modules.os.path.abspath(expanded))
    folder = localize(session.connection.modules.os.path.dirname(resolved))
    if folder:
        session.connection.modules.os.makedirs(folder, exist_ok=True)
    return resolved


def handle_screenshot(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        viewer = _resolve_scene_viewer(session, pane_name=args.pane_name, index=args.index)
        pane_name = localize(viewer.name())
        output_path = _resolve_output_path(session, args.output, pane_name)
        assetutils = session.connection.modules.husd.assetutils
        assetutils.saveThumbnailFromViewer(
            sceneviewer=viewer,
            frame=args.frame,
            res=(args.width, args.height),
            output=output_path,
        )
        exists = bool(localize(session.connection.modules.os.path.exists(output_path)))
        if not exists:
            raise ValueError(f"Screenshot was not written: {output_path}")
        size = int(localize(session.connection.modules.os.path.getsize(output_path)))
        return success_result(
            {
                "pane_name": pane_name,
                "path": output_path,
                "frame": int(args.frame),
                "width": int(args.width),
                "height": int(args.height),
                "bytes": size,
            }
        )
