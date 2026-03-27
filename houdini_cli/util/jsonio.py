"""JSON input helpers."""

from __future__ import annotations

import json
import sys
from typing import Any


def load_json_input(raw: str) -> Any:
    if raw == "-":
        return json.load(sys.stdin)
    return json.loads(raw)
