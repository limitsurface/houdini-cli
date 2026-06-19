"""Measure live Houdini CLI performance around `node get` sections.

The optional fixture creates a disposable SOP network with spare parameters and
child nodes so parameter snapshots and reference traversal can be measured
independently from any one production scene. Keep fixture sizes modest; very
large reference networks can stress Houdini while the CLI is under test.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any


DEFAULT_OPENCL_NODE = "/obj/copnet1/test_with_this"
DEFAULT_FIXTURE_ROOT = "/obj/cli_perf_node_get"
DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class Probe:
    name: str
    args: tuple[str, ...]
    timeout: float = DEFAULT_TIMEOUT


def _cli_executable() -> list[str]:
    local_package = Path(__file__).resolve().parents[1] / "houdini_cli" / "main.py"
    if local_package.exists():
        return [sys.executable, "-m", "houdini_cli.main"]
    direct = shutil.which("houdini-cli")
    if direct:
        return [direct]
    return [sys.executable, "-m", "houdini_cli.main"]


def _run_cli(command_prefix: list[str], args: tuple[str, ...], timeout: float) -> dict[str, Any]:
    start = time.perf_counter()
    proc = subprocess.run(
        [*command_prefix, *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    elapsed = time.perf_counter() - start
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    payload: dict[str, Any] | None = None
    ok = False
    data_keys: dict[str, Any] = {}
    if stdout:
        try:
            payload = json.loads(stdout)
            ok = bool(payload.get("ok")) and proc.returncode == 0
            data = payload.get("data", {})
            if isinstance(data, dict):
                value = data.get("value")
                data_keys = {
                    "section": data.get("section"),
                    "counts": data.get("counts"),
                    "value_type": type(value).__name__,
                    "value_count": len(value) if hasattr(value, "__len__") else None,
                }
        except json.JSONDecodeError:
            payload = None
    return {
        "args": list(args),
        "returncode": proc.returncode,
        "ok": ok,
        "elapsed_ms": round(elapsed * 1000.0, 3),
        "stdout_bytes": len(proc.stdout.encode("utf-8", errors="replace")),
        "stderr_bytes": len(proc.stderr.encode("utf-8", errors="replace")),
        "data": data_keys,
        "error_type": (payload or {}).get("error", {}).get("type") if isinstance(payload, dict) else None,
        "stderr_tail": stderr[-500:] if stderr else "",
        "stdout_tail": stdout[-500:] if stdout and not ok else "",
    }


def _setup_fixture(
    command_prefix: list[str],
    *,
    root_path: str,
    node_count: int,
    spare_count: int,
    timeout: float,
) -> dict[str, Any]:
    parent_path, root_name = root_path.rsplit("/", 1)
    code = f"""
import hou

parent = hou.node({parent_path!r})
if parent is None:
    raise RuntimeError('missing parent: ' + {parent_path!r})
old = parent.node({root_name!r})
if old is not None:
    old.destroy()

root = parent.createNode('geo', {root_name!r})
for child in list(root.children()):
    child.destroy()

anchor = root.createNode('null', 'anchor')
group = hou.ParmTemplateGroup()
folder = hou.FolderParmTemplate('perf_folder', 'Perf Spare Parms')
for index in range({spare_count}):
    name = 'spare{{:04d}}'.format(index)
    folder.addParmTemplate(hou.FloatParmTemplate(name, 'Spare {{:04d}}'.format(index), 1, default_value=(float(index),)))
group.append(folder)
anchor.setParmTemplateGroup(group)
anchor.setParms({{'spare{{:04d}}'.format(index): float(index) for index in range({spare_count})}})

previous = anchor
for index in range({node_count}):
    node = root.createNode('null', 'ref_{{:04d}}'.format(index))
    node.setInput(0, previous)
    group = node.parmTemplateGroup()
    group.append(hou.FloatParmTemplate('refvalue', 'Ref Value', 1))
    node.setParmTemplateGroup(group)
    node.parm('refvalue').setExpression('ch("../anchor/spare{{:04d}}")'.format(index % max({spare_count}, 1)))
    previous = node

root.layoutChildren()
print(root.path())
print(anchor.path())
print(len(root.children()))
print(len(anchor.parms()))
"""
    return _run_cli(command_prefix, ("eval", "--code", code), timeout)


def _probes(opencl_node: str, fixture_root: str) -> list[Probe]:
    fixture_anchor = f"{fixture_root}/anchor"
    return [
        Probe("opencl node get parms", ("node", "get", opencl_node, "--section", "parms")),
        Probe("opencl node get full", ("node", "get", opencl_node, "--section", "full")),
        Probe("opencl node get references", ("node", "get", opencl_node, "--section", "references")),
        Probe("fixture anchor get parms", ("node", "get", fixture_anchor, "--section", "parms")),
        Probe("fixture anchor get full", ("node", "get", fixture_anchor, "--section", "full")),
        Probe("fixture root get references", ("node", "get", fixture_root, "--section", "references")),
        Probe("fixture root get references external", ("node", "get", fixture_root, "--section", "references", "--external-only")),
    ]


def _summarize(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_name.setdefault(str(result["name"]), []).append(result)
    rows = []
    for name, items in by_name.items():
        timings = [float(item["elapsed_ms"]) for item in items]
        failures = [item for item in items if not item["ok"]]
        rows.append(
            {
                "name": name,
                "runs": len(items),
                "ok": len(failures) == 0,
                "failures": len(failures),
                "min_ms": min(timings),
                "median_ms": median(timings),
                "mean_ms": round(mean(timings), 3),
                "max_ms": max(timings),
                "stdout_bytes_median": median([int(item["stdout_bytes"]) for item in items]),
            }
        )
    return sorted(rows, key=lambda row: row["max_ms"], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opencl-node", default=DEFAULT_OPENCL_NODE)
    parser.add_argument("--fixture-root", default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--setup-fixture", action="store_true")
    parser.add_argument("--node-count", type=int, default=40)
    parser.add_argument("--spare-count", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    command_prefix = _cli_executable()
    setup_result = None
    if args.setup_fixture:
        setup_result = _setup_fixture(
            command_prefix,
            root_path=args.fixture_root,
            node_count=args.node_count,
            spare_count=args.spare_count,
            timeout=args.timeout,
        )
        status = "ok" if setup_result["ok"] else "FAIL"
        print(f"{status:4} {setup_result['elapsed_ms']:9.3f} ms  setup fixture", flush=True)
        if not setup_result["ok"]:
            print(json.dumps(setup_result, indent=2))
            return 1

    results: list[dict[str, Any]] = []
    for probe in _probes(args.opencl_node, args.fixture_root):
        for _index in range(args.iterations):
            result = _run_cli(command_prefix, probe.args, probe.timeout)
            result["name"] = probe.name
            results.append(result)
            status = "ok" if result["ok"] else "FAIL"
            print(f"{status:4} {result['elapsed_ms']:9.3f} ms  {probe.name}", flush=True)

    report = {
        "opencl_node": args.opencl_node,
        "fixture_root": args.fixture_root,
        "node_count": args.node_count,
        "spare_count": args.spare_count,
        "iterations": args.iterations,
        "setup": setup_result,
        "summary": _summarize(results),
        "results": results,
    }
    print("\nSummary:")
    print(json.dumps(report["summary"], indent=2))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json_out}")

    return 1 if any(not result["ok"] for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
