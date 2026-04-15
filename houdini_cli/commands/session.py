"""Session-oriented commands."""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize

_FCUR_FRAME_PATTERN = re.compile(r"Frame\s+(-?\d+(?:\.\d+)?)")
_VIEWPORT_AXIS_MAP = {
    "+x": "Right",
    "-x": "Left",
    "+y": "Top",
    "-y": "Bottom",
    "+z": "Front",
    "-z": "Back",
    "persp": "Perspective",
}


def _viewport_type_name(viewport) -> str:
    viewport_type = str(viewport.type())
    return viewport_type.rsplit(".", 1)[-1]


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
    _add_scene_viewer_selector_args(screenshot_parser)
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

    viewport_parser = session_subparsers.add_parser(
        "viewport",
        help="Read or manipulate the current Scene Viewer viewport.",
    )
    viewport_subparsers = viewport_parser.add_subparsers(dest="viewport_command", required=True)

    viewport_get_parser = viewport_subparsers.add_parser(
        "get",
        help="Read viewport type and free-camera state.",
    )
    _add_scene_viewer_selector_args(viewport_get_parser)
    viewport_get_parser.set_defaults(handler=handle_viewport_get)

    viewport_focus_parser = viewport_subparsers.add_parser(
        "focus-selected",
        help="Frame the current Scene Viewer selection, like Space+F.",
    )
    _add_scene_viewer_selector_args(viewport_focus_parser)
    viewport_focus_parser.set_defaults(handler=handle_viewport_focus_selected)

    viewport_axis_parser = viewport_subparsers.add_parser(
        "axis",
        help="Switch the viewport to a fixed orthographic axis view or perspective.",
    )
    _add_scene_viewer_selector_args(viewport_axis_parser)
    viewport_axis_parser.add_argument(
        "axis",
        choices=sorted(_VIEWPORT_AXIS_MAP.keys()),
        help="Axis shorthand: +x -x +y -y +z -z persp",
    )
    viewport_axis_parser.set_defaults(handler=handle_viewport_axis)

    viewport_set_parser = viewport_subparsers.add_parser(
        "set",
        help="Set free-camera translation, rotation, and optional pivot on the viewport.",
    )
    _add_scene_viewer_selector_args(viewport_set_parser)
    viewport_set_parser.add_argument(
        "--t",
        nargs=3,
        type=float,
        metavar=("X", "Y", "Z"),
        help="Absolute camera translation.",
    )
    viewport_set_parser.add_argument(
        "--r",
        nargs=3,
        type=float,
        metavar=("RX", "RY", "RZ"),
        help="Absolute camera rotation in degrees.",
    )
    viewport_set_parser.add_argument(
        "--pivot",
        nargs=3,
        type=float,
        metavar=("X", "Y", "Z"),
        help="Absolute camera pivot.",
    )
    viewport_set_parser.set_defaults(handler=handle_viewport_set)


def _add_scene_viewer_selector_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pane-name",
        help="Scene Viewer pane name, for example panetab1.",
    )
    parser.add_argument(
        "--index",
        type=int,
        help="Scene Viewer index from the current desktop ordering.",
    )


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


def _resolve_viewport(session, *, pane_name: str | None, index: int | None):
    viewer = _resolve_scene_viewer(session, pane_name=pane_name, index=index)
    viewport = viewer.curViewport()
    if viewport is None:
        raise ValueError("Scene Viewer has no active viewport")
    return viewer, viewport


def _viewport_camera_payload(viewer, viewport) -> dict:
    camera = viewport.defaultCamera()
    return {
        "pane_name": localize(viewer.name()),
        "viewport_name": localize(viewport.name()),
        "viewport_type": str(viewport.type()),
        "is_perspective": bool(camera.isPerspective()),
        "translation": [float(value) for value in camera.translation()],
        "pivot": [float(value) for value in camera.pivot()],
        "rotation": [float(value) for value in camera.rotation().extractRotates()],
    }


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


def handle_viewport_get(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        viewer, viewport = _resolve_viewport(session, pane_name=args.pane_name, index=args.index)
        return success_result(_viewport_camera_payload(viewer, viewport))


def handle_viewport_focus_selected(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        viewer, viewport = _resolve_viewport(session, pane_name=args.pane_name, index=args.index)
        viewport.frameSelected()
        viewport.draw()
        payload = _viewport_camera_payload(viewer, viewport)
        payload["action"] = "focus-selected"
        return success_result(payload)


def handle_viewport_axis(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        viewer, viewport = _resolve_viewport(session, pane_name=args.pane_name, index=args.index)
        viewport_type = getattr(session.hou.geometryViewportType, _VIEWPORT_AXIS_MAP[args.axis])
        viewport.changeType(viewport_type)
        viewport.draw()
        payload = _viewport_camera_payload(viewer, viewport)
        payload["action"] = "axis"
        payload["axis"] = args.axis
        return success_result(payload)


def handle_viewport_set(args: argparse.Namespace) -> dict:
    if args.t is None and args.r is None and args.pivot is None:
        raise ValueError("Provide at least one of --t, --r, or --pivot")

    with connect(args.host, args.port) as session:
        viewer, viewport = _resolve_viewport(session, pane_name=args.pane_name, index=args.index)
        if _viewport_type_name(viewport) != "Perspective":
            raise ValueError("Viewport camera set only supports perspective views; use session viewport axis persp first")

        camera = viewport.defaultCamera()
        if args.r is not None:
            rotation = session.hou.hmath.buildRotate(tuple(float(value) for value in args.r)).extractRotationMatrix3()
            camera.setRotation(rotation)
        if args.t is not None:
            camera.setTranslation(tuple(float(value) for value in args.t))
        if args.pivot is not None:
            camera.setPivot(tuple(float(value) for value in args.pivot))
        viewport.draw()

        payload = _viewport_camera_payload(viewer, viewport)
        payload["action"] = "set"
        return success_result(payload)
