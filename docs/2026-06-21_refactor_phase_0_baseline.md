# Refactor Phase 0 Baseline

Date: 2026-06-21

This baseline supports `docs/2026-06-21_code_refactor_checklist.md`. It records the contracts and live checks that should remain stable through the refactor.

## Automated Tests

- Command: `.venv/Scripts/python.exe -m pytest`
- Result: `180 passed in 2.05s`
- Note: `uv run pytest` failed before test collection with `Failed to canonicalize script path`; the repository virtual environment completed normally.

## Live Test HDA

- Selected/current node: `/obj/geo1/copnet1/ntsc_hou1`
- Selection count: `1`
- HDA definition: current
- Instance state: locked and matching its current definition
- Interface size: `143` parameters
- Connected inputs/outputs: `1` / `1`
- External-reference baseline: `0` external, `0` absolute internal, `493` ordinary internal references

The selected node is the default target for the smoke matrix. Tests must rediscover the current selection rather than assuming the path remains available in a later Houdini session.

## Import And Ownership Baseline

- `houdini_cli/main.py` imports the `parm` command module for parser registration.
- `tests/test_parm.py` imports the `parm` module and directly exercises its private helpers.
- `tests/test_hda_validate.py` directly exercises `hda_validate._external_reference_rows`.
- No production module imports the private reference helpers currently defined in `parm.py` or `hda_validate.py`.
- Phase 1 may move private helper tests to `parm_refs`, but parser handlers and command contracts remain owned by `parm.py` and `hda_validate.py`.

## Output Contracts

### `parm find`

- Data keys: `node`, `query`, `count`, `items`
- Meta keys: `limit`, `truncated`
- Item identity: `parm_path`, `name`, `tuple`, `type`, `matches`
- Optional item details: `raw`, `expression`, `language`, `resolved_targets`
- Baseline query `ch` with all details and limit `20`: `20` items, truncated

### `parm refs`

- Data keys: `node`, `external_to`, `recursive`, `count`, `items`
- Meta keys: `limit`, `truncated`
- Item keys: `from_parm`, `to_parm`, plus `external` when `--external-to` is supplied
- Baseline recursive scan with limit `100`: `100` items, truncated; sampled references are internal

### `hda validate --external-references`

- Existing validation fields remain unchanged.
- Reference audit keys: `root`, `count`, `items`, `absolute_internal_count`, `absolute_internal`, `internal_count`, `reference_count`
- Baseline result: validation `ok`, `0` external references and `493` total references

### Help

- `help parm find`, `help parm refs`, and `help hda validate` return successful JSON help envelopes.
- Usage strings include all current reference flags.

## Performance Baseline

The broad suite first ran its `20` pre-existing probes for three iterations against the selected HDA. All probes succeeded and remained below the `750 ms` slow threshold. The slowest median was `hda definitions Scy` at `352.155 ms`.

Focused reference timings used five independent CLI process runs:

| Command | Minimum ms | Median ms | Maximum ms |
| --- | ---: | ---: | ---: |
| `parm find` with raw, expression, and target details | 153.850 | 158.930 | 171.550 |
| recursive `parm refs`, limited to 100 | 163.440 | 164.980 | 174.660 |
| `hda validate --external-references` | 502.910 | 527.160 | 540.110 |

After adding the three reference probes, all `23` probes passed for three iterations. Their medians were `146.017 ms` for parameter search, `160.832 ms` for recursive references, and `480.501 ms` for HDA reference validation. Refactor comparisons should use repeated runs and treat normal process/session timing noise as noise, not a regression.

## Smoke Matrix

| Area | Required smoke check |
| --- | --- |
| Parameter search | Run `parm find` with raw, expression, and resolved-target details; compare count, truncation, and representative rows. |
| Parameter references | Run `parm refs` recursively with an external root; compare count, truncation, and representative internal/external flags. |
| HDA validation | Run external-reference validation; compare all audit counts and validation status. |
| OpenCL | Run sync and validate checks when OpenCL code changes; include spare preservation on and off. |
| Node references | Run the references section with and without external filtering when node reference code changes. |
| Help | Query affected group and leaf topics after parser/help changes. |

## Phase Gates

- Focused unit tests pass.
- Full automated suite passes.
- Affected live smoke rows and counts remain equivalent.
- Relevant benchmark medians show no material regression across repeated runs.
- Any unavailable live context is recorded rather than silently skipped.
