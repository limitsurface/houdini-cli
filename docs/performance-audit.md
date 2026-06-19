# Houdini CLI Performance Audit

Date: 2026-06-19

This note records performance risks found during a first broad pass over the
CLI command implementations. The motivating issue was `node parms find/list`
being extremely slow on an OpenCL COP with many generated parameters.

## Confirmed Issue: Broad Parm Discovery

The original `node parms find/list` implementation looped through `node.parms()`
from the client and made several RPyC calls per parameter:

- `parm.parmTemplate().type().name()`
- `parm.tuple()`
- `parm.valueAsData()`
- `parm.isAtDefault()`

On `/obj/copnet1/test_with_this`, a narrow query:

```text
node parms find /obj/copnet1/test_with_this --name pause --max-parms 20 --values
```

took roughly 15 seconds before the fix. Manual timing inside one Houdini eval
showed the HOM operations themselves were cheap:

```text
4 pause parms valueAsData(): ~0.04 ms
5 parms valueAsData():      ~0.05 ms
node.parms names only:      <1 ms
```

So the problem was RPyC round-trip amplification, not `valueAsData()` itself.

The fix batches parm row construction into a single Houdini-side eval. After
the change, the same query with values returned in roughly 167-184 ms.

## Audit Pattern

Potentially expensive command implementations usually fall into one of these
patterns:

- Per-parameter or per-node loops where each iteration calls HOM through RPyC.
- Broad value extraction using `valueAsData()`, `eval()`, `evalAsString()`,
  `isAtDefault()`, or template access from the client side.
- Forced cooks in read-oriented commands.
- Large structured snapshots with `parmsAsData()` or `asData()`.
- Recursive scene traversal such as `allSubChildren()` or broad reference scans.
- Repeated `parmTemplateGroup()` / `setParmTemplateGroup()` operations.

The general fix is to batch the loop inside Houdini and return plain Python
data in one result. Targeted single-parameter commands are usually fine.

## HDA Commands

The newer HDA commands have several similar risks.

### `hda parms inspect`

File: `houdini_cli/commands/hda_parms.py`

`handle_parms_inspect` calls `definition.parmTemplateGroup().entries()` and
then walks templates through `_flat_parm_rows()`. When `--values` is enabled,
it calls `node.parm(name).eval()` per published parameter from the client.

Risk: medium to high on HDAs with many parameters, multiparms, or expensive
parameter expressions.

Suggested fix: move `_flat_parm_rows()` into a Houdini-side eval, similar to
the fixed `node parms` path. Keep folder/name filtering inside that eval.

### `hda parms locate`

File: `houdini_cli/commands/hda_parms.py`

`handle_parms_locate` currently calls `_flat_parm_rows(..., include_values=True,
include_defaults=True)` across the whole parameter interface, then filters for
the exact name.

Risk: high for large HDAs because it computes values/defaults for many parms
to locate one parm.

Suggested fix: look up the exact template/name first and only evaluate the
matching parameter. Prefer a Houdini-side helper that returns one row.

### `hda parms defaults`

File: `houdini_cli/commands/hda_parms.py`

`handle_parms_defaults --from-current` loops over `node.parms()`, calls
`parm.tuple()`, and evaluates each tuple component from the client.

Risk: high on nodes with many parms or expression-driven defaults.

Suggested fix: execute the full loop in Houdini and return only the updated
count/library. This command mutates HDA definitions, so batching also reduces
the window for partial remote failures.

### `hda parms promote`

File: `houdini_cli/commands/hda_parms.py`

When `--default current` is used, it evaluates the internal parm on the client.
This is targeted, so it is less concerning than broad scans.

Risk: low to medium. It can still cook if the internal parm expression is
expensive.

Suggested fix: no urgent change, but if this command grows more logic, keep
template mutation and default capture in one Houdini-side helper.

### `hda inspect --parms` and `hda parms folders`

Files:

- `houdini_cli/commands/hda_inspect.py`
- `houdini_cli/commands/hda_parms.py`

These walk `definition.parmTemplateGroup().entries()` and recursively read
template names/labels/types. This is metadata-only but still does multiple
remote calls per template.

Risk: medium for large HDA interfaces.

Suggested fix: batch `parm_tree()` / folder-row construction inside Houdini.

## Node Commands

### `node get --section parms`

File: `houdini_cli/commands/node.py`

Uses:

```python
node.parmsAsData(brief=False)
```

Risk: high. This can materialize a large structured parameter payload and may
evaluate values depending on HOM behavior.

Suggested fix: document this as a heavy/full snapshot path, or add a compact
section implemented with the new fast parm-row helper.

### `node get --section full`

File: `houdini_cli/commands/node.py`

Uses `node.asData(... parms=True ...)`.

Risk: high. This is expected to be heavy, but it should remain clearly marked
as a full snapshot command.

Suggested fix: keep as explicit full mode. Consider adding warnings in help
text and avoid calling it from automated workflows unless requested.

### `node errors`

File: `houdini_cli/commands/node.py`

Currently force-cooks every inspected node before reading messages:

```python
node.cook(force=True)
```

Risk: high for COP/OpenCL, simulations, render-like nodes, or expensive SOPs.
In the OpenCL COP test it was not slow, but the behavior is inherently risky
for a read-looking command.

Suggested fix: make cooking opt-in, e.g. `node errors --cook`, and default to
reading existing `errors()/warnings()/messages()` only.

### `node get --section references`

File: `houdini_cli/commands/node.py`

Uses `root.allSubChildren()` and calls `parameter.references()` for every parm
on every node.

Risk: medium to high on large networks.

Suggested fix: add caps/depth controls or move traversal into Houdini with a
timeout. Keep `--external-only`, but do filtering in the same in-process loop.

## OpenCL Commands

File: `houdini_cli/commands/opencl.py`

OpenCL sync/validate already do domain-specific work and are expected to be
heavier than simple reads. Observed timings on the test COP were roughly
650-825 ms for validate.

Potential hot spots:

- `_validation_summary()` calls `_safe_cook()`.
- `_existing_signature_entries()` uses `opencl_node.parmsAsData(brief=False)`.
- Binding row summaries use several `parm.eval()` / `evalAsString()` calls.
- Sync modifies parameter template groups to create generated spare controls.

Risk: medium to high, depending on node type and upstream cook cost.

Suggested fixes:

- Consider `opencl validate --no-cook` or make cook opt-in.
- Replace `parmsAsData()` signature reads with direct multiparm reads or a
  Houdini-side compact signature helper.
- Batch binding row summaries in Houdini when validating existing rows.

## HDA Lifecycle Commands

File: `houdini_cli/commands/hda_lifecycle.py`

The lifecycle commands are mostly mutation commands, so heavier operations are
more expected. Still, `handle_update` captures `node.parmTemplateGroup()` and
preserves section contents before update. `validate_asset(... cook=True)` is
called for package/update validation paths.

Risk: medium. The operations are intentionally heavier, but should not be used
as cheap inspection.

Suggested fix: keep validation/cooking behind explicit flags where possible.
For update workflows, avoid reading interface/sections/tools unless requested.

## HDA Validation

File: `houdini_cli/commands/hda_validate.py`

`validate_asset()` can create a fresh instance, set frame, force cook, and then
report messages and counts.

Risk: high when `--cook`, frames, or fresh instances are used, but this is an
explicit validation command.

Suggested fix: document that cook validation is expensive. Avoid calling it
implicitly from commands unless the user passed validation-related flags.

## Query / Traversal Commands

File: `houdini_cli/commands/query.py`

`node list/find/neighbors` are capped by default and use traversal timeouts,
which is good. However, `node_summary()` performs several remote calls per
node (`children`, `inputs`, `outputs`, flags, type/category).

Risk: low to medium with current caps, higher if users raise `--max-nodes`.

Suggested fix: if traversal performance becomes an issue, batch summaries
inside Houdini-side traversal and return rows directly.

## Recommended Priorities

1. Batch HDA parameter inspection/locate/defaults inside Houdini.
2. Make `node errors` cooking opt-in.
3. Add fast compact alternatives for `node get --section parms/full`, or mark
   them clearly as heavy snapshot commands.
4. Reduce `opencl validate` reliance on `parmsAsData()` and consider a
   no-cook mode.
5. Keep using scripts for regression timing:

```text
python scripts/audit_perf_hotspots.py
python scripts/perf_probe_opencl_cop.py
```

## Rule of Thumb

If a command loops over many HOM objects, the loop should generally run inside
Houdini and return plain JSON-like data. Client-side loops over remote HOM
objects are acceptable for targeted operations, but not for broad scans.
