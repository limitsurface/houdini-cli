# `houdini-cli opencl sync` Fix Plan

## Goal

Make `houdini-cli opencl sync` safe to use on non-trivial COP OpenCL nodes.

This plan is focused on behavior and implementation. Help/discoverability changes are intentionally out of scope for this pass.

## Live Repro Summary

System-installed CLI was used against a live Houdini session with a disposable repro node under:

- `/obj/fixes_here/copnet1/opencl_sync_repro`
- `/obj/fixes_here/copnet1/opencl_sync_repro2`

Representative kernel:

```c
#bind layer !size_ref?
#bind layer stamp0
#bind layer stamp1?
#bind layer stamp2?
#bind layer stamp3?
#bind layer cam
#bind point geoP name=P port=geo float3
#bind point geopscale? name=pscale port=geo float val=1
#bind point geoid? name=id port=geo int
#bind point geostamp? name=stamp port=geo int
#bind layer !&dst
#bind layer !&depth float
#bind layer !&id int
#bind parm radius float val=0.02
#bind parm hard_alpha float val=1.0
#bind parm stamp_seed float val=0.0
```

Observed on a fresh node before sync:

- `inputs = 1`
- `outputs = 1`
- `bindings = 0`
- visible signature still reflected the node factory defaults

Observed after `houdini-cli opencl sync /obj/fixes_here/copnet1/opencl_sync_repro`:

- visible inputs became:
  - `stamp0`
  - `stamp1`
  - `stamp2`
  - `stamp3`
  - `cam`
  - `geoP`
  - `geopscale`
  - `geoid`
  - `geostamp`
- `size_ref` disappeared from visible inputs
- outputs became `dst`, `depth`, `id`
- spare parms were created for `radius`, `hard_alpha`, `stamp_seed`
- binding multiparm rows were cross-polluted after a single sync:
  - `size_ref` row carried `pscale`-style `volume` / `attribute` / `fval`
  - `stamp0` row carried `id`-style fields
  - `cam` row carried `stamp_seed`-style parm data

Conclusion: the command is currently destructive in exactly the workflow it is meant to support.

## Existing-Node Edit Repro

The more important production case was also tested: modifying an already-synced node with a large existing binding table.

Test node:

- `/obj/fixes_here/copnet1/opencl_edit_repro`

Sequence:

1. create fresh node with the mixed-bind kernel above
2. run `houdini-cli opencl sync /obj/fixes_here/copnet1/opencl_edit_repro`
3. modify the existing kernel by adding one new parm bind:

```c
#bind parm extra_bias float val=0.5
```

4. run `houdini-cli opencl sync /obj/fixes_here/copnet1/opencl_edit_repro` again

Observed after the second sync:

- visible inputs were still the broken 9-input signature
- spare parms were extended to include `extra_bias`
- the new parm data polluted an unrelated existing binding row:
  - `geoP` now carried `bindings#_volume = "extra_bias"`
  - `geoP` also carried `bindings#_fval = ch("./extra_bias")`

This confirms the destructive behavior is not limited to first-time sync. The command becomes less trustworthy as existing nodes evolve.

## Current Root Causes

## 1. Visible input generation is derived from raw readable bindings

Current code in [`houdini_cli/commands/opencl.py`](../houdini_cli/commands/opencl.py):

- `_apply_signature()` builds `input_bindings` by including every readable binding whose type is `layer`, `attribute`, `volume`, or `vdb`
- it then writes one visible input row per binding

That means:

- every readable `attribute` bind becomes a visible geometry input
- multiple binds with `portname='geo'` are not collapsed
- metadata/reference binds with `readable=False` are dropped entirely

This is the direct cause of the broken signature.

## 2. Metadata support exists in type mapping but is unreachable

`_signature_type()` knows about `metadata`, but `_apply_signature()` never includes metadata bindings in `input_bindings`.

For `#bind layer !size_ref?`, Houdini bind extraction returns a `layer` binding with `readable=False`, not a `metadata` binding the current filter can route into the visible signature.

Result:

- `size_ref` is consistently excluded
- metadata/reference inputs are not preserved

## 3. Spare parm generation likely dirties node state mid-sync

Current flow:

1. `_sync_spare_parms()` clears `inputs`, `outputs`, and `bindings`
2. it calls Houdini's `createSpareParmsFromOCLBindings(...)`
3. `_apply_signature()` later rewrites counts and multiparm values

The live repro shows polluted multiparm rows after a single sync. The most likely causes are:

- Houdini's spare-parm helper mutates OpenCL binding state internally
- the CLI then writes a partial row model on top of a dirty multiparm table
- incompatible per-type fields are left behind on rows

Even if the helper is only partly responsible, the current sequence is unsafe because it allows hidden intermediate mutation and then performs a non-atomic rebuild.

## 4. Binding row writes are not normalized per row kind

`_binding_parm_values()` only writes fields relevant to the current binding type. That is reasonable if rows are clean, but unsafe if rows were previously used for another binding kind.

Result:

- stale `volume`, `attribute`, `attribtype`, `fval`, `intval`, and related fields survive on later rows
- `node get --section parms` becomes misleading and hard to trust
- adding a single new parm bind to an existing node can contaminate an unrelated pre-existing attribute row

## Fix Strategy

Use a staged fix. Do not try to solve everything with one refactor.

## Phase 1: Make sync non-destructive

Primary objective: stop breaking working nodes.

Changes:

1. Add `--bindings-only`
2. Make `--bindings-only` update:
   - binding rows
   - generated spare parms
   - `options_runover`
3. Make `--bindings-only` leave visible inputs/outputs untouched

Why first:

- this gives users an immediate safe path
- it reduces blast radius while deeper signature logic is corrected
- it matches the real production need: keep a curated signature, refresh binds/parms

CLI shape:

```powershell
houdini-cli opencl sync <node-path> --bindings-only
```

Behavior:

- default `sync` can remain as the full rebuild path temporarily
- advanced users immediately get a safe recovery workflow

## Phase 2: Replace raw-binding signature generation with port-model generation

Primary objective: derive visible inputs from semantic ports, not individual binds.

Implementation:

1. Parse Houdini-extracted bindings into an internal model:
   - input layers
   - output layers
   - geometry ports
   - volume ports
   - vdb ports
   - parm binds
   - metadata/reference binds
2. Group readable geometry/attribute binds by `portname`
3. Emit one visible input per unique input port
4. Preserve layer ordering from kernel bind order
5. Emit metadata/reference inputs explicitly

Expected visible inputs for the repro kernel:

1. `size_ref` as metadata/reference input
2. `stamp0`
3. `stamp1`
4. `stamp2`
5. `stamp3`
6. `cam`
7. `geo` as geometry

Rules:

- `#bind point ... port=geo ...` does not create multiple visible inputs
- optional attributes remain only in binding rows
- output layers continue to map one-to-one

## Phase 3: Preserve compatible existing signatures by default

Primary objective: avoid reinterpreting valid existing wiring.

Implementation:

1. Read current visible inputs/outputs before rebuild
2. Match desired rows to existing rows by semantic key:
   - port kind
   - port name
   - IO direction
3. Preserve order for compatible existing rows where possible
4. Only append, remove, or reorder rows when required by actual semantic changes

This should become the default behavior for full sync.

Fallback:

- if the existing signature is incompatible or ambiguous, rebuild deterministically and report that a rebuild occurred

## Phase 4: Rebuild binding rows from a clean slate

Primary objective: eliminate polluted multiparm rows.

Implementation options:

### Preferred

- clear `bindings` count to `0`
- set `bindings` count to final row count
- write all rows from a normalized model
- explicitly initialize all type-sensitive fields per row kind

### If Houdini requires additional cleanup

- clear counts
- force a cook or parameter update point if needed
- then rebuild rows in one pass

Normalization rules:

- every row kind gets a known baseline field set
- fields not valid for the row kind are explicitly reset
- do not rely on prior multiparm state

This is the fix for the stale row contamination seen in the live repro.

## Phase 5: Decouple spare parm generation from signature mutation

Primary objective: stop hidden side effects from the spare-parm helper from contaminating sync.

Short-term option:

- keep the helper only for generated spare parm UI if it proves safe after binding rows are rebuilt last

Safer option:

- stop using Houdini's helper for this command
- generate spare parm templates directly from extracted parm binds
- insert/update only the generated parameter folder

Recommendation:

- move toward the direct/manual spare-parm path
- use the helper only if it can be proven not to mutate binding/signature state

The current code already has a manual fallback path. Expand that into the primary path if needed.

## Proposed Implementation Order

1. Add `--bindings-only`
2. Refactor sync into separate steps:
   - extract bindings
   - build internal model
   - sync binding rows
   - sync spare parms
   - sync visible signature
3. Switch binding-row rebuild to clean-slate writes
4. Replace raw-binding input generation with grouped-port generation
5. Add existing-signature preservation
6. Reassess whether Houdini helper-based spare-parm generation should remain

## Test Plan

## Unit tests

Add tests for:

- multiple `attribute` binds sharing one `portname` collapse into one visible geometry input
- metadata/reference layer binds are retained in visible inputs
- optional geometry attributes do not create extra visible inputs
- `--bindings-only` does not change `inputs` or `outputs`
- binding row generation resets incompatible fields across mixed row kinds
- full sync preserves compatible existing signature rows where possible

## Integration-style command tests

Extend [`tests/test_opencl.py`](../tests/test_opencl.py) to cover:

- mixed layer + attribute + parm kernels
- metadata layer input kernels
- full sync summary output
- bindings-only summary output

Add explicit assertions against:

- returned `inputs`
- returned `outputs`
- returned `spare_parms`
- the `setParms()` payload shape and ordering

## Live validation

Re-test in Houdini on disposable nodes under `/obj/fixes_here/copnet1`:

1. Fresh node with mixed kernel
2. Full sync
3. Verify visible inputs are `size_ref, stamp0, stamp1, stamp2, stamp3, cam, geo`
4. Verify only one geometry input is created
5. Verify binding rows no longer carry cross-assigned fields
6. Verify `--bindings-only` updates spare parms without touching curated signature rows

## Acceptance Criteria

`opencl sync` is acceptable again when all of the following are true:

- a mixed COP kernel does not create fake geometry inputs for attribute binds
- metadata/reference inputs are retained
- binding rows are clean after sync
- adding a new parm bind does not semantically reinterpret existing valid wiring
- adding a new parm bind to an already-synced node does not contaminate any existing binding rows
- users have a safe `--bindings-only` mode for production workflows

## Recommendation

Implement Phase 1 and Phase 4 first.

That combination gives the fastest practical recovery:

- users regain a non-destructive sync mode immediately
- multiparm pollution is addressed at the same time

After that, implement grouped-port signature generation and preservation logic so full sync becomes safe enough to use on real COP kernels.
