"""Network Editor navigation commands."""

from __future__ import annotations

import argparse

from ..format.envelopes import success_result
from ..transport.rpyc import connect, localize
from .node_common import get_node


def _get_parent_path(node) -> str:
    parent = node.parent()
    if parent is None:
        raise ValueError(f"Node has no parent network: {localize(node.path())}")
    return localize(parent.path())


def _get_network_editor(session):
    if not session.hou.isUIAvailable():
        raise ValueError("Houdini UI is not available")

    for pane_tab in session.hou.ui.paneTabs():
        if all(hasattr(pane_tab, name) for name in ("setPwd", "setCurrentNode", "frameSelection")):
            return pane_tab
    raise ValueError("No Network Editor pane is available")


def handle_nav(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        nodes = [get_node(session, node_path) for node_path in args.node_paths]
        parent_paths = {_get_parent_path(node) for node in nodes}
        if len(parent_paths) != 1:
            raise ValueError("Nodes do not share the same parent network")

        network_editor = _get_network_editor(session)
        network = get_node(session, parent_paths.pop())
        network_editor.setPwd(network)

        selected = not args.no_select
        frame = not args.no_frame
        set_current = not args.no_current

        if selected or frame:
            for index, target_node in enumerate(nodes):
                target_node.setSelected(True, clear_all_selected=index == 0)
        else:
            network_editor.clearAllSelected()

        if set_current:
            network_editor.setCurrentNode(nodes[-1])

        framed = False
        if frame:
            network_editor.frameSelection()
            framed = True

        if not selected:
            network_editor.clearAllSelected()

        return success_result(
            {
                "network": localize(network.path()),
                "nodes": [localize(node.path()) for node in nodes],
                "selected": selected,
                "current": localize(nodes[-1].path()) if set_current else None,
                "framed": framed,
            }
        )
