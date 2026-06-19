"""Measure live Houdini CLI performance around HDA parameter commands.

The script can create a disposable HDA fixture from an existing OpenCL COP node
and then time the HDA parameter inspection commands against that instance.
It talks to a running Houdini session and is intentionally separate from pytest.
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


DEFAULT_SOURCE_NODE = "/obj/copnet1/test_with_this"
DEFAULT_ASSET_NODE = "/obj/copnet1/hda_perf_opencl_shake"
DEFAULT_LIBRARY = "work/hda_perf_opencl_shake.hda"
DEFAULT_TIMEOUT = 30.0


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
    if stdout:
        try:
            payload = json.loads(stdout)
            ok = bool(payload.get("ok")) and proc.returncode == 0
        except json.JSONDecodeError:
            payload = None
    return {
        "args": list(args),
        "returncode": proc.returncode,
        "ok": ok,
        "elapsed_ms": round(elapsed * 1000.0, 3),
        "stdout_bytes": len(proc.stdout.encode("utf-8", errors="replace")),
        "stderr_bytes": len(proc.stderr.encode("utf-8", errors="replace")),
        "error_type": (payload or {}).get("error", {}).get("type") if isinstance(payload, dict) else None,
        "stderr_tail": stderr[-500:] if stderr else "",
        "stdout_tail": stdout[-500:] if stdout and not ok else "",
    }


def _setup_fixture(
    command_prefix: list[str],
    *,
    source_node: str,
    asset_node: str,
    library: Path,
    timeout: float,
) -> dict[str, Any]:
    library = library.resolve()
    library.parent.mkdir(parents=True, exist_ok=True)
    asset_parent, asset_name = asset_node.rsplit("/", 1)
    code = f"""
import os
import hou

src = hou.node({source_node!r})
if src is None:
    raise RuntimeError('missing source node: ' + {source_node!r})
parent = hou.node({asset_parent!r})
if parent is None:
    raise RuntimeError('missing asset parent: ' + {asset_parent!r})

for name in ({asset_name!r}, {asset_name + '_src'!r}):
    old = parent.node(name)
    if old is not None:
        old.destroy()

subnet = parent.createNode('subnet', {asset_name + '_src'!r})
copied = hou.copyNodesTo((src,), subnet)[0]
copied.setName('opencl_shake', unique_name=True)
copied.moveToGoodPosition()
library = {str(library)!r}
os.makedirs(os.path.dirname(library), exist_ok=True)
asset = subnet.createDigitalAsset(
    name='codex::hda_perf_opencl_shake::1.0',
    hda_file_name=library,
    description='Codex HDA Perf OpenCL Shake',
)
asset.setName({asset_name!r}, unique_name=True)
definition = asset.type().definition()
definition.setParmTemplateGroup(src.parmTemplateGroup())
asset.matchCurrentDefinition()
print(asset.path())
print(asset.type().name())
print(definition.libraryFilePath())
print(len(asset.parms()))
"""
    return _run_cli(command_prefix, ("eval", "--code", code), timeout)


def _probes(asset_node: str) -> list[Probe]:
    return [
        Probe("hda parms folders", ("hda", "parms", "folders", asset_node)),
        Probe("hda parms inspect", ("hda", "parms", "inspect", asset_node)),
        Probe("hda parms inspect values", ("hda", "parms", "inspect", asset_node, "--values")),
        Probe("hda parms inspect defaults", ("hda", "parms", "inspect", asset_node, "--defaults")),
        Probe("hda parms inspect values defaults", ("hda", "parms", "inspect", asset_node, "--values", "--defaults")),
        Probe("hda parms find pause values defaults", ("hda", "parms", "find", asset_node, "--name", "pause", "--values", "--defaults")),
        Probe("hda parms locate pause_amp", ("hda", "parms", "locate", asset_node, "pause_amp")),
        Probe("hda inspect parms", ("hda", "inspect", asset_node, "--parms")),
    ]


def _run_probe(command_prefix: list[str], probe: Probe) -> dict[str, Any]:
    result = _run_cli(command_prefix, probe.args, probe.timeout)
    result["name"] = probe.name
    return result


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
            }
        )
    return sorted(rows, key=lambda row: row["max_ms"], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-node", default=DEFAULT_SOURCE_NODE)
    parser.add_argument("--asset-node", default=DEFAULT_ASSET_NODE)
    parser.add_argument("--library", type=Path, default=Path(DEFAULT_LIBRARY))
    parser.add_argument("--setup-fixture", action="store_true")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    command_prefix = _cli_executable()
    setup_result = None
    if args.setup_fixture:
        setup_result = _setup_fixture(
            command_prefix,
            source_node=args.source_node,
            asset_node=args.asset_node,
            library=args.library,
            timeout=args.timeout,
        )
        status = "ok" if setup_result["ok"] else "FAIL"
        print(f"{status:4} {setup_result['elapsed_ms']:9.3f} ms  setup fixture", flush=True)
        if not setup_result["ok"]:
            print(json.dumps(setup_result, indent=2))
            return 1

    results: list[dict[str, Any]] = []
    for probe in _probes(args.asset_node):
        for _index in range(args.iterations):
            result = _run_probe(command_prefix, probe)
            results.append(result)
            status = "ok" if result["ok"] else "FAIL"
            print(f"{status:4} {result['elapsed_ms']:9.3f} ms  {probe.name}", flush=True)

    report = {
        "source_node": args.source_node,
        "asset_node": args.asset_node,
        "library": str(args.library),
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
