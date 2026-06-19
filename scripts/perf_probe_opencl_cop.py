"""Measure live Houdini CLI performance around OpenCL COP inspection paths.

This script is intentionally separate from pytest: it talks to a running
Houdini session and may trigger cooks. By default it uses the duplicated node
from the camera-shake investigation:

    /obj/copnet1/test_with_this

Examples:

    uv run python scripts/perf_probe_opencl_cop.py
    uv run python scripts/perf_probe_opencl_cop.py --iterations 5 --json-out perf.json
    uv run python scripts/perf_probe_opencl_cop.py --include-risky

The default probe avoids the broad parm-list path that previously crashed
Houdini. Pass --include-risky when you explicitly want to time it.
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


DEFAULT_NODE = "/obj/copnet1/test_with_this"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class Probe:
    name: str
    args: tuple[str, ...]
    risky: bool = False
    timeout: float = DEFAULT_TIMEOUT


def _cli_executable() -> list[str]:
    local_package = Path(__file__).resolve().parents[1] / "houdini_cli" / "main.py"
    if local_package.exists():
        return [sys.executable, "-m", "houdini_cli.main"]
    direct = shutil.which("houdini-cli")
    if direct:
        return [direct]
    return [sys.executable, "-m", "houdini_cli.main"]


def _probes(node_path: str) -> list[Probe]:
    return [
        Probe("ping", ("ping",), timeout=10.0),
        Probe("targeted parm get kernelcode", ("parm", "get", f"{node_path}/kernelcode")),
        Probe("targeted parm get pause_amp", ("parm", "get", f"{node_path}/pause_amp")),
        Probe("template get pause_amp", ("parm", "template", "get", f"{node_path}/pause_amp")),
        Probe("node connections", ("node", "connections", node_path)),
        Probe("opencl validate compact", ("opencl", "validate", node_path)),
        Probe("opencl validate details", ("opencl", "validate", node_path, "--details")),
        Probe("node errors", ("node", "errors", node_path)),
        Probe("node parms find pause values", ("node", "parms", "find", node_path, "--name", "pause", "--max-parms", "20")),
        Probe("node parms list 45", ("node", "parms", "list", node_path, "--max-parms", "45"), risky=True),
        Probe(
            "node parms list 200 non-default",
            ("node", "parms", "list", node_path, "--non-default", "--max-parms", "200"),
            risky=True,
        ),
        Probe("node get section parms", ("node", "get", node_path, "--section", "parms"), risky=True),
        Probe("node get full", ("node", "get", node_path, "--section", "full"), risky=True),
    ]


def _run_probe(command_prefix: list[str], probe: Probe) -> dict[str, Any]:
    start = time.perf_counter()
    proc = subprocess.run(
        [*command_prefix, *probe.args],
        text=True,
        capture_output=True,
        timeout=probe.timeout,
        check=False,
    )
    elapsed = time.perf_counter() - start
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    ok = False
    payload: dict[str, Any] | None = None
    if stdout:
        try:
            payload = json.loads(stdout)
            ok = bool(payload.get("ok")) and proc.returncode == 0
        except json.JSONDecodeError:
            payload = None
    return {
        "name": probe.name,
        "args": list(probe.args),
        "risky": probe.risky,
        "returncode": proc.returncode,
        "ok": ok,
        "elapsed_ms": round(elapsed * 1000.0, 3),
        "stdout_bytes": len(proc.stdout.encode("utf-8", errors="replace")),
        "stderr_bytes": len(proc.stderr.encode("utf-8", errors="replace")),
        "error_category": (payload or {}).get("error", {}).get("category") if isinstance(payload, dict) else None,
        "error_type": (payload or {}).get("error", {}).get("type") if isinstance(payload, dict) else None,
        "stderr_tail": stderr[-500:] if stderr else "",
        "stdout_tail": stdout[-500:] if (stdout and not ok) else "",
    }


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
                "risky": bool(items[0]["risky"]),
            }
        )
    return sorted(rows, key=lambda row: row["max_ms"], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=DEFAULT_NODE, help=f"OpenCL COP path. Default: {DEFAULT_NODE}")
    parser.add_argument("--iterations", type=int, default=3, help="Runs per probe.")
    parser.add_argument("--include-risky", action="store_true", help="Include broad parm/node reads that may cook heavily.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Default per-command timeout in seconds.")
    parser.add_argument("--json-out", type=Path, help="Optional path for the full JSON report.")
    args = parser.parse_args()

    command_prefix = _cli_executable()
    probes = [
        Probe(probe.name, probe.args, probe.risky, args.timeout if probe.timeout == DEFAULT_TIMEOUT else probe.timeout)
        for probe in _probes(args.node)
        if args.include_risky or not probe.risky
    ]

    results: list[dict[str, Any]] = []
    for probe in probes:
        for _index in range(args.iterations):
            result = _run_probe(command_prefix, probe)
            results.append(result)
            status = "ok" if result["ok"] else "FAIL"
            print(f"{status:4} {result['elapsed_ms']:9.3f} ms  {probe.name}", flush=True)

    report = {
        "node": args.node,
        "iterations": args.iterations,
        "include_risky": args.include_risky,
        "summary": _summarize(results),
        "results": results,
    }
    print("\nSummary:")
    print(json.dumps(report["summary"], indent=2))

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json_out}")

    return 1 if any(not result["ok"] for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
