"""Typed assembly and execution for internal Houdini-side scripts."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping


def python_literal(value: Any) -> str:
    """Encode transport-safe values as deterministic Python literals."""
    if value is None or isinstance(value, (bool, int, str)):
        return repr(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Remote arguments must use finite floats")
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(python_literal(item) for item in value) + "]"
    if isinstance(value, tuple):
        items = ", ".join(python_literal(item) for item in value)
        return f"({items},)" if len(value) == 1 else f"({items})"
    if isinstance(value, dict):
        items = ", ".join(
            f"{python_literal(key)}: {python_literal(item)}"
            for key, item in value.items()
        )
        return "{" + items + "}"
    raise TypeError(f"Unsupported remote argument type: {type(value).__name__}")


@dataclass(frozen=True)
class RemoteModule:
    """Install one script and call its explicitly registered entrypoints."""

    namespace: str
    source: str
    entrypoints: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.namespace.isidentifier():
            raise ValueError(f"Invalid remote namespace: {self.namespace}")
        if not self.source.strip():
            raise ValueError("Remote module source must not be empty")
        for alias, function_name in self.entrypoints.items():
            if not alias.isidentifier():
                raise ValueError(f"Invalid remote entrypoint alias: {alias}")
            if not function_name.startswith("_houdini_cli_") or not function_name.isidentifier():
                raise ValueError(f"Invalid remote function name: {function_name}")

    def call(self, entrypoint: str, *args: Any) -> str:
        try:
            function_name = self.entrypoints[entrypoint]
        except KeyError as exc:
            raise KeyError(
                f"Unknown {self.namespace} remote entrypoint: {entrypoint}"
            ) from exc
        encoded = ", ".join(python_literal(arg) for arg in args)
        return f"{function_name}({encoded})"

    def install(self, connection: Any) -> None:
        connection.execute(self.source)

    def evaluate(self, connection: Any, entrypoint: str, *args: Any) -> Any:
        self.install(connection)
        return connection.eval(self.call(entrypoint, *args))
