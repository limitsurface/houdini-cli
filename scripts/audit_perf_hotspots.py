"""Static audit for Houdini CLI performance hot spots.

The audit is heuristic. It looks for HOM calls that often trigger cooks,
parameter evaluation, or large remote object localization. Use it to guide
manual review, not as a hard pass/fail linter.

Example:

    uv run python scripts/audit_perf_hotspots.py
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_ROOT = Path("houdini_cli")


@dataclass(frozen=True)
class Pattern:
    name: str
    severity: str
    hint: str


CALL_PATTERNS = {
    "cook": Pattern("forced cook", "high", "Avoid force-cooking during read-only inspection, or make it opt-in."),
    "valueAsData": Pattern(
        "parm valueAsData",
        "high",
        "Evaluates parameter values. Prefer template/name/type metadata unless values are requested.",
    ),
    "asData": Pattern(
        "asData/parmsAsData",
        "high",
        "Can materialize large structured payloads. Keep behind explicit --full/--values flags.",
    ),
    "parmsAsData": Pattern("node parmsAsData", "high", "Can materialize and evaluate a large parm payload."),
    "eval": Pattern("parm eval", "medium", "May evaluate expressions/cook dependencies. Prefer evalAsString only when required."),
    "evalAsString": Pattern("parm evalAsString", "medium", "May evaluate expressions. Fine for targeted reads; risky in broad loops."),
    "isAtDefault": Pattern(
        "parm isAtDefault",
        "medium",
        "Can be surprisingly expensive in broad parm scans; consider opt-in non-default checks.",
    ),
    "allSubChildren": Pattern("recursive node traversal", "medium", "Can traverse large scenes. Keep capped or scoped."),
    "references": Pattern("parm references", "medium", "Can be expensive across many parms. Keep scoped and optional."),
    "parmTemplateGroup": Pattern("parm template group", "medium", "Template groups can be large remote objects. Prefer focused operations."),
    "setParmTemplateGroup": Pattern("set parm template group", "medium", "Mutates node UI and can trigger rebuilds. Batch changes where possible."),
}


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
    return "<module>"


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    result: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            result[child] = parent
    return result


def _python_files(root: Path) -> Iterable[Path]:
    yield from sorted(path for path in root.rglob("*.py") if path.is_file())


def audit_file(path: Path) -> list[dict[str, object]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    parents = _parents(tree)
    lines = source.splitlines()
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node)
        if call_name not in CALL_PATTERNS:
            continue
        pattern = CALL_PATTERNS[call_name]
        findings.append(
            {
                "file": str(path),
                "line": node.lineno,
                "function": _enclosing_function(node, parents),
                "call": call_name,
                "name": pattern.name,
                "severity": pattern.severity,
                "hint": pattern.hint,
                "source": lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else "",
            }
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()

    findings: list[dict[str, object]] = []
    for path in _python_files(args.root):
        findings.extend(audit_file(path))

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda item: (severity_order.get(str(item["severity"]), 99), str(item["file"]), int(item["line"])))

    if args.json:
        print(json.dumps({"count": len(findings), "findings": findings}, indent=2))
        return 0

    print(f"Found {len(findings)} potential hot spots.\n")
    for item in findings:
        print(f"{item['severity'].upper():6} {item['file']}:{item['line']}  {item['function']}  {item['name']}")
        print(f"       {item['source']}")
        print(f"       {item['hint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
