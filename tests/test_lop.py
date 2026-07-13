from argparse import Namespace

import pytest

from houdini_cli.commands import lop
from houdini_cli.remote.lop_stage import LOP_STAGE_REMOTE


def _args(**overrides):
    values = {
        "output": 0,
        "max_depth": None,
        "max_prims": 10000,
        "top_types": 20,
    }
    values.update(overrides)
    return Namespace(**values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"output": -1}, "Output index"),
        ({"max_depth": -1}, "Maximum depth"),
        ({"max_prims": 0}, "Maximum prims"),
        ({"top_types": 0}, "Top types"),
    ],
)
def test_validate_args_rejects_invalid_bounds(overrides, message) -> None:
    with pytest.raises(ValueError, match=message):
        lop._validate_args(_args(**overrides))


def test_remote_summary_call_encodes_all_limits() -> None:
    call = LOP_STAGE_REMOTE.call(
        "summary", "/stage/OUT", 1, 4, 5000, 12, True, 50
    )

    assert call == "_houdini_cli_lop_stage_summary('/stage/OUT', 1, 4, 5000, 12, True, 50)"


def test_remote_source_uses_all_prim_predicate_and_excludes_instance_proxies() -> None:
    source = LOP_STAGE_REMOTE.source

    assert "Usd.PrimAllPrimsPredicate" in source
    assert '"outputConnectors"' in source
    assert '"instance_proxies": "excluded"' in source
    assert "TraverseInstanceProxies" not in source
    assert '"counts_complete": not truncated' in source
