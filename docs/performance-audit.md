# Houdini CLI Performance Audit

Date: 2026-06-19

This note records performance risks found during a first broad pass over the
CLI command implementations. The motivating issue was `node parms find/list`
being extremely slow on an OpenCL COP with many generated parameters.

## Completed Work

The first optimization pass produced these commits:

- `cd36693` - batch `node parms list/find` discovery and value/default reads.
- `d698f03` - batch HDA parameter inspection, lookup, folder listing, and
  `hda inspect --parms`.
- `5d042d8` - batch `hda parms defaults --from-current`.
- `9ba4334` - make `node errors` cooking explicit via `--cook`.
- `ae75a01` - batch OpenCL COP validation reads.
- `d12244b` - batch `node get --section references`.

Live benchmark evidence came from Houdini 21.0.729 against the camera-shake
test scene, primarily `/obj/copnet1/test_with_this`. The broad pattern held
across command families: the expensive cases were usually not the underlying
HOM operations, but many small RPyC calls or broad HOM snapshot APIs.

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

Status: fixed in `cd36693`.

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

Status: fixed in `d698f03`.

Live fixture: copied the OpenCL shake node into a disposable COP subnet HDA and
copied its parameter interface onto the HDA definition.

Observed timings:

```text
hda parms inspect values:          ~427-460 ms -> ~153-158 ms
hda parms inspect values defaults: ~402-458 ms -> ~151-175 ms
hda parms find pause values defs:  ~304-358 ms -> ~157-159 ms
```

### `hda parms locate`

File: `houdini_cli/commands/hda_parms.py`

`handle_parms_locate` currently calls `_flat_parm_rows(..., include_values=True,
include_defaults=True)` across the whole parameter interface, then filters for
the exact name.

Risk: high for large HDAs because it computes values/defaults for many parms
to locate one parm.

Suggested fix: look up the exact template/name first and only evaluate the
matching parameter. Prefer a Houdini-side helper that returns one row.

Status: fixed in `d698f03` by moving the flat row construction and filtering
into Houdini.

Observed timing:

```text
hda parms locate pause_amp: ~317-331 ms -> ~157-168 ms
```

### `hda parms defaults`

File: `houdini_cli/commands/hda_parms.py`

`handle_parms_defaults --from-current` loops over `node.parms()`, calls
`parm.tuple()`, and evaluates each tuple component from the client.

Risk: high on nodes with many parms or expression-driven defaults.

Suggested fix: execute the full loop in Houdini and return only the updated
count/library. This command mutates HDA definitions, so batching also reduces
the window for partial remote failures.

Status: fixed in `5d042d8`.

Observed timing:

```text
hda parms defaults --from-current: ~840-915 ms -> ~341-366 ms
```

### `hda parms promote`

File: `houdini_cli/commands/hda_parms.py`

When `--default current` is used, it evaluates the internal parm on the client.
This is targeted, so it is less concerning than broad scans.

Risk: low to medium. It can still cook if the internal parm expression is
expensive.

Suggested fix: no urgent change, but if this command grows more logic, keep
template mutation and default capture in one Houdini-side helper.

Status: not changed. This remains a targeted operation, not a broad scan.

### `hda inspect --parms` and `hda parms folders`

Files:

- `houdini_cli/commands/hda_inspect.py`
- `houdini_cli/commands/hda_parms.py`

These walk `definition.parmTemplateGroup().entries()` and recursively read
template names/labels/types. This is metadata-only but still does multiple
remote calls per template.

Risk: medium for large HDA interfaces.

Suggested fix: batch `parm_tree()` / folder-row construction inside Houdini.

Status: fixed in `d698f03`.

Observed timings:

```text
hda parms folders:  ~283-286 ms -> ~150-154 ms
hda inspect --parms: ~402-415 ms -> ~189-195 ms
```

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

Status: not changed. Benchmarks showed this is a broad HOM snapshot API cost,
not only an RPyC-loop cost.

Observed timings on `/obj/copnet1/test_with_this`:

```text
node get --section parms: ~346-363 ms
hou.OpNode.parmsAsData(brief=False) inside Houdini: ~152-188 ms
direct node.parms() value scan inside Houdini: ~1 ms
```

Do not silently replace this section with the compact parm-row helper because
the JSON schema would change. A future command or section for compact parameter
rows would be reasonable if users need this behavior.

### `node get --section full`

File: `houdini_cli/commands/node.py`

Uses `node.asData(... parms=True ...)`.

Risk: high. This is expected to be heavy, but it should remain clearly marked
as a full snapshot command.

Suggested fix: keep as explicit full mode. Consider adding warnings in help
text and avoid calling it from automated workflows unless requested.

Status: not changed. This remains an explicit full snapshot path.

Observed timings on `/obj/copnet1/test_with_this`:

```text
node get --section full: ~343-353 ms
hou.OpNode.asData(...) inside Houdini: ~150-167 ms
```

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

Status: fixed in `9ba4334`.

Observed timings on the test OpenCL COP were roughly the same with and without
cooking, around 157-178 ms. The change was kept because it avoids accidental
expensive cooks on heavier nodes without bloating unrelated commands.

### `node get --section references`

File: `houdini_cli/commands/node.py`

Uses `root.allSubChildren()` and calls `parameter.references()` for every parm
on every node.

Risk: medium to high on large networks.

Suggested fix: add caps/depth controls or move traversal into Houdini with a
timeout. Keep `--external-only`, but do filtering in the same in-process loop.

Status: fixed in `d12244b` by moving the traversal and filtering into Houdini.

Observed timings on `/obj/copnet1/test_with_this`:

```text
node get --section references: ~2627-2758 ms, then EOF/crash risk -> ~157-170 ms
```

A deliberately large temporary reference fixture also stressed Houdini during
benchmarking. The committed `scripts/perf_probe_node_get.py` now defaults to a
smaller fixture and should be scaled up carefully.

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

- Replace `parmsAsData()` signature reads with direct multiparm reads or a
  Houdini-side compact signature helper.
- Batch binding row summaries in Houdini when validating existing rows.

Status: fixed for COP validation in `ae75a01` without adding command-line
flags. Cook/no-cook was not split because in-Houdini cook timing on the test
COP was sub-millisecond and the user preferred not adding arguments for minimal
performance differences.

Live sub-step timings showed:

```text
node.cook(force=True):             ~0.2 ms
kernel eval + oclExtractBindings:  <1 ms
parmsAsData inputs:                ~152-186 ms
parmsAsData outputs:               ~153-165 ms
direct signature multiparm reads:  ~0.01 ms
```

Observed command timings:

```text
opencl validate compact baseline:       mean ~656 ms
after direct signature reads:            mean ~338 ms
after batched validation state reads:    mean ~190-196 ms
opencl validate --details final:         mean ~187-200 ms
```

Remaining note: SOP/DOP OpenCL validation paths still use their existing
targeted row readers. They were not part of this COP-focused benchmark.

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

1. Decide whether to add a separate compact snapshot command/section for node
   parameters. Do not change `node get --section parms/full` silently because
   callers may rely on the HOM snapshot schema.
2. Audit SOP/DOP OpenCL validation separately if those become active
   workflows.
3. Consider batching `query.node_summary()` if large `node list/find` calls
   become slow with raised caps.
4. Keep using scripts for regression timing:

```text
python scripts/audit_perf_hotspots.py
python scripts/perf_probe_opencl_cop.py
python scripts/perf_probe_hda_parms.py
python scripts/perf_probe_node_get.py
```

## Rule of Thumb

If a command loops over many HOM objects, the loop should generally run inside
Houdini and return plain JSON-like data. Client-side loops over remote HOM
objects are acceptable for targeted operations, but not for broad scans.
