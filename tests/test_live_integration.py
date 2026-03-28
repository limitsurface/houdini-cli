import json
import socket
import uuid

import pytest

from houdini_cli.main import main


def _server_available(host: str = "localhost", port: int = 18811) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _run_cli(args, capsys):
    exit_code = main(args)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    return exit_code, payload, captured


@pytest.mark.skipif(not _server_available(), reason="Live Houdini hrpyc server not available")
def test_live_cli_workflow(capsys) -> None:
    token = uuid.uuid4().hex[:8]
    obj_path = f"/obj/cli_live_suite_{token}"
    out_path = f"{obj_path}/OUT"
    cleanup_code = f"""
node = hou.node('{obj_path}')
if node is not None:
    node.destroy()
"""
    setup_code = f"""
obj = hou.node('/obj')
existing = obj.node('cli_live_suite_{token}')
if existing is not None:
    existing.destroy()
geo = obj.createNode('geo', 'cli_live_suite_{token}')
box = geo.createNode('box', 'box1')
wrangle = geo.createNode('attribwrangle', 'attribwrangle1')
wrangle.setInput(0, box)
wrangle.parm('class').set('point')
wrangle.parm('snippet').set('f@pscale = @ptnum * 0.5;')
out = geo.createNode('null', 'OUT')
out.setInput(0, wrangle)
out.setDisplayFlag(True)
out.setRenderFlag(True)
geo.layoutChildren()
print(out.path())
"""
    try:
        exit_code, payload, _ = _run_cli(["eval", "--code", setup_code], capsys)
        assert exit_code == 0
        assert out_path in payload["data"]["stdout"]

        exit_code, payload, _ = _run_cli(["ping"], capsys)
        assert exit_code == 0
        assert payload["ok"] is True

        exit_code, payload, _ = _run_cli(["eval", "--code", "print(hou.applicationVersionString())"], capsys)
        assert exit_code == 0
        assert payload["data"]["stdout"].strip()

        exit_code, payload, _ = _run_cli(["node", "create", obj_path, "null", "--name", "temp_cli"], capsys)
        assert exit_code == 0
        temp_node_path = payload["data"]["path"]

        exit_code, payload, _ = _run_cli(["node", "delete", temp_node_path], capsys)
        assert exit_code == 0
        assert payload["data"]["deleted"] is True

        exit_code, payload, _ = _run_cli(["parm", "get", f"{obj_path}/box1/sizex"], capsys)
        assert exit_code == 0
        assert payload["ok"] is True

        exit_code, payload, _ = _run_cli(["parm", "set", f"{obj_path}/box1/sizex", "--json", "2.5"], capsys)
        assert exit_code == 0
        assert payload["data"]["applied"] is True

        exit_code, payload, _ = _run_cli(["parm", "get", f"{obj_path}/box1/sizex"], capsys)
        assert exit_code == 0
        assert payload["data"]["value"] == [2.5, 1.0, 1.0]

        exit_code, payload, _ = _run_cli(["attrib", "list", out_path, "--class", "point"], capsys)
        assert exit_code == 0
        point_names = [item["name"] for item in payload["data"]["classes"]["point"]]
        assert "pscale" in point_names

        exit_code, payload, _ = _run_cli(["attrib", "get", out_path, "pscale", "--class", "point", "--element", "3"], capsys)
        assert exit_code == 0
        assert payload["data"]["value"]["element"] == 3
        assert payload["data"]["value"]["value"] == 1.5

        exit_code, payload, _ = _run_cli(["nodetype", "find", "--category", "sop", "--query", "wrangle", "--limit", "10"], capsys)
        assert exit_code == 0
        assert any(item["key"] == "attribwrangle" for item in payload["data"]["items"])

        exit_code, payload, _ = _run_cli(["nodetype", "get", "--category", "sop", "attribwrangle"], capsys)
        assert exit_code == 0
        assert payload["data"]["name"] == "attribwrangle"
    finally:
        exit_code, payload, _ = _run_cli(["eval", "--code", cleanup_code], capsys)
        assert exit_code == 0
