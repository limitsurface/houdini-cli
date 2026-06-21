"""Run a broad live Houdini CLI performance benchmark suite.

This script is intentionally outside pytest because it talks to a running
Houdini session. It is meant to find areas of concern, not to fail CI on small
timing changes.

Examples:

    uv run python scripts/perf_benchmark_suite.py
    uv run python scripts/perf_benchmark_suite.py --iterations 5 --json-out work/perf/latest.json
    uv run python scripts/perf_benchmark_suite.py --include-risky --markdown-out work/perf/latest.md
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


DEFAULT_TIMEOUT = 30.0
DEFAULT_SLOW_MS = 750.0
DEFAULT_VERY_SLOW_MS = 1500.0


@dataclass(frozen=True)
class Probe:
    name: str
    args: tuple[str, ...]
    tags: tuple[str, ...] = ()
    risky: bool = False
    timeout: float = DEFAULT_TIMEOUT
    requires: tuple[str, ...] = ()


@dataclass
class Context:
    selected_node: str | None = None
    selected_parent: str | None = None
    selected_root: str = "/obj"
    is_hda: bool = False

    def format_args(self, args: tuple[str, ...]) -> tuple[str, ...]:
        values = {
            "selected": self.selected_node or "",
            "selected_parent": self.selected_parent or self.selected_root,
            "selected_root": self.selected_root,
        }
        return tuple(arg.format(**values) for arg in args)


def _cli_executable() -> list[str]:
    local_package = Path(__file__).resolve().parents[1] / "houdini_cli" / "main.py"
    if local_package.exists():
        return [sys.executable, "-m", "houdini_cli.main"]
    direct = shutil.which("houdini-cli")
    if direct:
        return [direct]
    return [sys.executable, "-m", "houdini_cli.main"]


def _run_cli(command_prefix: list[str], args: tuple[str, ...], timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [*command_prefix, *args],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        elapsed = time.perf_counter() - started
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "args": list(args),
            "returncode": None,
            "ok": False,
            "timed_out": True,
            "elapsed_ms": round(elapsed * 1000.0, 3),
            "stdout_bytes": len(stdout.encode("utf-8", errors="replace")),
            "stderr_bytes": len(stderr.encode("utf-8", errors="replace")),
            "error_category": "timeout",
            "error_type": "subprocess.TimeoutExpired",
            "stderr_tail": stderr[-500:],
            "stdout_tail": stdout[-500:],
        }

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    payload: dict[str, Any] | None = None
    ok = False
    data_shape: dict[str, Any] = {}
    if stdout:
        try:
            payload = json.loads(stdout)
            ok = bool(payload.get("ok")) and proc.returncode == 0
            data = payload.get("data")
            if isinstance(data, dict):
                data_shape = {
                    "data_keys": sorted(str(key) for key in data.keys())[:20],
                    "count": data.get("count"),
                    "section": data.get("section"),
                }
        except json.JSONDecodeError:
            payload = None

    return {
        "args": list(args),
        "returncode": proc.returncode,
        "ok": ok,
        "timed_out": False,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "stdout_bytes": len(proc.stdout.encode("utf-8", errors="replace")),
        "stderr_bytes": len(proc.stderr.encode("utf-8", errors="replace")),
        "data_shape": data_shape,
        "error_category": (payload or {}).get("error", {}).get("category") if isinstance(payload, dict) else None,
        "error_type": (payload or {}).get("error", {}).get("type") if isinstance(payload, dict) else None,
        "stderr_tail": stderr[-500:] if stderr else "",
        "stdout_tail": stdout[-500:] if stdout and not ok else "",
    }


def _run_json(command_prefix: list[str], args: tuple[str, ...], timeout: float = 10.0) -> dict[str, Any] | None:
    try:
        proc = subprocess.run(
            [*command_prefix, *args],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return payload if payload.get("ok") else None


def _discover_context(command_prefix: list[str], requested_node: str | None) -> Context:
    selected = requested_node
    if selected is None:
        payload = _run_json(command_prefix, ("session", "selection"), timeout=10.0)
        data = payload.get("data", {}) if payload else {}
        selected = data.get("current") if isinstance(data, dict) else None

    context = Context(selected_node=selected)
    if selected:
        context.selected_parent = selected.rsplit("/", 1)[0] or "/"
        parts = selected.strip("/").split("/")
        context.selected_root = "/" + "/".join(parts[:2]) if len(parts) >= 2 else "/obj"
        context.is_hda = _run_json(command_prefix, ("hda", "inspect", selected), timeout=15.0) is not None
    return context


def _base_probes() -> list[Probe]:
    return [
        Probe("ping", ("ping",), tags=("core",), timeout=10.0),
        Probe("session selection", ("session", "selection"), tags=("session",), timeout=10.0),
        Probe("shelf list", ("shelf", "list"), tags=("discovery", "shelf")),
        Probe("shelf find Scy", ("shelf", "find", "--query", "Scy"), tags=("discovery", "shelf")),
        Probe("recipe list", ("recipe", "list", "--limit", "50"), tags=("discovery", "recipe")),
        Probe("recipe find Scy", ("recipe", "find", "--query", "Scy", "--limit", "50"), tags=("discovery", "recipe")),
        Probe("nodetype list cop", ("nodetype", "list", "--category", "cop", "--limit", "50"), tags=("discovery", "nodetype")),
        Probe("hda libraries scyTools", ("hda", "libraries", "--library", "scyTools", "--max", "50"), tags=("discovery", "hda")),
        Probe("hda definitions Scy", ("hda", "definitions", "--namespace", "Scy", "--max", "50"), tags=("discovery", "hda")),
        Probe(
            "node find selected parent",
            ("node", "find", "{selected_parent}", "--max-depth", "2", "--max-nodes", "100"),
            tags=("traversal", "node"),
            requires=("selected",),
        ),
        Probe(
            "node list selected parent",
            ("node", "list", "{selected_parent}", "--max-depth", "1", "--max-nodes", "100"),
            tags=("traversal", "node"),
            requires=("selected",),
        ),
        Probe(
            "node get selected",
            ("node", "get", "{selected}"),
            tags=("node", "targeted"),
            requires=("selected",),
        ),
        Probe(
            "node connections selected",
            ("node", "connections", "{selected}"),
            tags=("node", "targeted"),
            requires=("selected",),
        ),
        Probe(
            "node errors selected",
            ("node", "errors", "{selected}"),
            tags=("node", "targeted"),
            requires=("selected",),
        ),
        Probe(
            "node parms find selected",
            ("node", "parms", "find", "{selected}", "--name", "amp", "--max-parms", "20"),
            tags=("parm", "targeted"),
            requires=("selected",),
        ),
        Probe(
            "node parms list selected",
            ("node", "parms", "list", "{selected}", "--max-parms", "100"),
            tags=("parm",),
            requires=("selected",),
        ),
        Probe(
            "parm find selected references",
            (
                "parm",
                "find",
                "{selected}",
                "--query",
                "ch",
                "--raw",
                "--expressions",
                "--resolved-targets",
                "--max-matches",
                "20",
            ),
            tags=("parm", "references", "targeted"),
            requires=("selected",),
        ),
        Probe(
            "parm refs selected recursive",
            (
                "parm",
                "refs",
                "{selected}",
                "--external-to",
                "{selected}",
                "--recursive",
                "--max-refs",
                "100",
            ),
            tags=("parm", "references", "traversal"),
            requires=("selected",),
        ),
        Probe(
            "hda inspect selected",
            ("hda", "inspect", "{selected}"),
            tags=("hda", "targeted"),
            requires=("hda",),
        ),
        Probe(
            "hda section list selected",
            ("hda", "section", "list", "{selected}"),
            tags=("hda", "sections"),
            requires=("hda",),
        ),
        Probe(
            "hda parms inspect selected",
            ("hda", "parms", "inspect", "{selected}"),
            tags=("hda", "parm"),
            requires=("hda",),
        ),
        Probe(
            "hda parms folders selected",
            ("hda", "parms", "folders", "{selected}"),
            tags=("hda", "parm"),
            requires=("hda",),
        ),
        Probe(
            "hda validate selected references",
            ("hda", "validate", "{selected}", "--external-references"),
            tags=("hda", "parm", "references", "validation"),
            requires=("hda",),
        ),
        Probe(
            "node get selected parms snapshot",
            ("node", "get", "{selected}", "--section", "parms"),
            tags=("node", "snapshot"),
            risky=True,
            requires=("selected",),
        ),
        Probe(
            "node get selected full snapshot",
            ("node", "get", "{selected}", "--section", "full"),
            tags=("node", "snapshot"),
            risky=True,
            requires=("selected",),
        ),
        Probe(
            "hda definitions Scy with sections",
            ("hda", "definitions", "--namespace", "Scy", "--max", "50", "--sections"),
            tags=("discovery", "hda", "sections"),
            risky=True,
        ),
    ]


def _probe_available(probe: Probe, context: Context, include_risky: bool) -> bool:
    if probe.risky and not include_risky:
        return False
    if "selected" in probe.requires and not context.selected_node:
        return False
    if "hda" in probe.requires and not context.is_hda:
        return False
    return True


def _summary(results: list[dict[str, Any]], slow_ms: float, very_slow_ms: float) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(str(result["name"]), []).append(result)

    rows = []
    for name, items in grouped.items():
        timings = [float(item["elapsed_ms"]) for item in items]
        failures = [item for item in items if not item["ok"]]
        max_ms = max(timings)
        concern = "ok"
        if failures:
            concern = "failure"
        elif max_ms >= very_slow_ms:
            concern = "very_slow"
        elif median(timings) >= slow_ms:
            concern = "slow"
        rows.append(
            {
                "name": name,
                "tags": items[0]["tags"],
                "risky": items[0]["risky"],
                "runs": len(items),
                "ok": len(failures) == 0,
                "failures": len(failures),
                "min_ms": round(min(timings), 3),
                "median_ms": round(median(timings), 3),
                "mean_ms": round(mean(timings), 3),
                "max_ms": round(max_ms, 3),
                "stdout_bytes_median": median([int(item["stdout_bytes"]) for item in items]),
                "concern": concern,
            }
        )
    concern_order = {"failure": 0, "very_slow": 1, "slow": 2, "ok": 3}
    return sorted(rows, key=lambda row: (concern_order[str(row["concern"])], -float(row["max_ms"])))


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Houdini CLI Performance Benchmark",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Iterations: {report['iterations']}",
        f"- Include risky: {report['include_risky']}",
        f"- Selected node: {report['context'].get('selected_node') or '(none)'}",
        f"- Selected node is HDA: {report['context'].get('is_hda')}",
        "",
        "## Ranked Summary",
        "",
        "| Concern | Probe | Median ms | Max ms | Runs | Tags |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in report["summary"]:
        lines.append(
            "| {concern} | {name} | {median_ms:.3f} | {max_ms:.3f} | {runs} | {tags} |".format(
                concern=row["concern"],
                name=row["name"],
                median_ms=float(row["median_ms"]),
                max_ms=float(row["max_ms"]),
                runs=int(row["runs"]),
                tags=", ".join(row["tags"]),
            )
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", help="Node to use for selected-node probes. Defaults to Houdini's current selection.")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--include-risky", action="store_true")
    parser.add_argument("--slow-ms", type=float, default=DEFAULT_SLOW_MS)
    parser.add_argument("--very-slow-ms", type=float, default=DEFAULT_VERY_SLOW_MS)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    if args.iterations <= 0:
        raise ValueError("--iterations must be positive")

    command_prefix = _cli_executable()
    context = _discover_context(command_prefix, args.node)
    probes = [
        probe
        for probe in _base_probes()
        if _probe_available(probe, context, include_risky=args.include_risky)
    ]

    print(f"Selected node: {context.selected_node or '(none)'}")
    print(f"Selected node is HDA: {context.is_hda}")
    print(f"Running {len(probes)} probes x {args.iterations} iterations\n")

    results: list[dict[str, Any]] = []
    for probe in probes:
        formatted_args = context.format_args(probe.args)
        for _index in range(args.iterations):
            result = _run_cli(command_prefix, formatted_args, args.timeout if probe.timeout == DEFAULT_TIMEOUT else probe.timeout)
            result.update(
                {
                    "name": probe.name,
                    "tags": list(probe.tags),
                    "risky": probe.risky,
                }
            )
            results.append(result)
            status = "ok" if result["ok"] else "FAIL"
            print(f"{status:4} {result['elapsed_ms']:9.3f} ms  {probe.name}", flush=True)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "iterations": args.iterations,
        "include_risky": args.include_risky,
        "slow_ms": args.slow_ms,
        "very_slow_ms": args.very_slow_ms,
        "context": {
            "selected_node": context.selected_node,
            "selected_parent": context.selected_parent,
            "selected_root": context.selected_root,
            "is_hda": context.is_hda,
        },
        "summary": _summary(results, args.slow_ms, args.very_slow_ms),
        "results": results,
    }

    print("\nRanked summary:")
    print(json.dumps(report["summary"], indent=2))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json_out}")
    if args.markdown_out:
        _write_markdown(report, args.markdown_out)
        print(f"Wrote {args.markdown_out}")

    return 1 if any(not result["ok"] for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
