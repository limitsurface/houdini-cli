# Code Refactor Checklist

Date: 2026-06-21

Source: `docs/2026-06-21_code_refactor_candidates.md`

Scope: production code under `houdini_cli/`. The goal is to reduce module size and ownership overlap without changing command syntax, output contracts, Houdini behavior, or supported fallback paths.

## Working Rules

- [ ] Keep each extraction behavior-preserving; do not combine it with feature work unless the feature is required to expose an existing boundary.
- [ ] Preserve public parser registration, handler names, JSON shapes, exit codes, and human-readable output.
- [ ] Preserve both local/fallback execution and Houdini remote execution where both exist.
- [ ] Keep commits small enough that an extraction can be reverted independently.
- [ ] Run the focused unit tests after each extraction.
- [ ] Run the full test suite before completing each phase.
- [ ] Smoke-test affected commands against a live selected test HDA before completing each phase that changes remote Houdini code.
- [ ] Record any intentionally deferred duplication or follow-up discovered during an extraction.
- [ ] Avoid compatibility re-export layers unless an existing import or test requires them.

## Phase 0: Baseline And Guardrails

- [x] Record the current full-suite result and test count.
- [x] Identify direct imports from each module scheduled for extraction.
- [x] Capture representative JSON and text output for affected commands before moving code.
- [x] Confirm the live smoke-test HDA and selected-node assumptions.
- [x] Define a short smoke matrix for parameter references, HDA validation, OpenCL sync/validate, node references, and help traversal.
- [x] Confirm no performance benchmark regresses materially after each high-priority phase.

Exit criteria:

- [x] Baseline tests, outputs, and live smoke commands are documented well enough to compare after each extraction.

## Phase 1: Shared Parameter Reference Logic

Target modules: `parm.py`, new `parm_refs.py`, and `hda_validate.py`.

- [x] Inventory reference parsing, safe parm reads, expression inspection, path resolution, and internal/external classification in `parm.py` and `hda_validate.py`.
- [x] Define the shared reference data model and ownership boundary.
- [x] Create `houdini_cli/commands/parm_refs.py`.
- [x] Move channel-reference parsing and target resolution into `parm_refs.py`.
- [x] Move raw/expression fallback readers into `parm_refs.py` where their behavior is genuinely shared.
- [x] Move root containment and external-reference classification into `parm_refs.py`.
- [x] Move `parm find` and `parm refs` implementation helpers into `parm_refs.py`.
- [x] Keep parser registration and thin command dispatch in `parm.py`.
- [x] Reuse the shared resolver from `hda_validate.py`.
- [x] Remove superseded duplicate helpers from `parm.py` and `hda_validate.py`.
- [x] Add or update focused tests for direct references, expression fallback references, recursive traversal, missing targets, and internal/external classification.
- [x] Compare representative JSON and text output with the baseline.
- [x] Smoke-test `parm find`, `parm refs`, recursive refs, and `hda validate --external-references` against the selected HDA.
- [x] Run the full test suite.

Exit criteria:

- [x] `parm.py` and `hda_validate.py` consume one reference resolver without changing their command contracts.

## Phase 2: OpenCL Spare Parameter Extraction

Target modules: `opencl.py` and new `opencl_spares.py`.

- [x] Inventory generated spare-template creation, removal, synchronization, value capture/restore, and link-expression helpers.
- [x] Create `houdini_cli/commands/opencl_spares.py`.
- [x] Move generated spare parameter UI/template helpers into `opencl_spares.py`.
- [x] Move spare value capture and restore logic into `opencl_spares.py`.
- [x] Move generated value-link expression helpers into `opencl_spares.py`.
- [x] Keep COP/SOP/DOP orchestration in `opencl.py` during this phase.
- [x] Preserve `--preserve-spare-values` behavior and default behavior exactly.
- [x] Add or update focused tests for template generation, removal, linking, preservation, and tuple/scalar values.
- [x] Compare sync and validate output with the baseline.
- [x] Smoke-test OpenCL sync and validate, including preservation on and off, against the selected HDA.
- [x] Run the relevant performance benchmark and investigate any material regression.
- [x] Run the full test suite.

Exit criteria:

- [x] Spare parameter behavior has one cohesive owner and `opencl.py` is smaller without changing context-specific behavior.

## Phase 3: Cross-Cutting Remote Script Infrastructure

Target area: raw Houdini-side Python embedded across command modules.

- [x] Inventory embedded remote scripts in `opencl.py`, `parm.py`, `hda_validate.py`, `node.py`, `hda_parms.py`, `query.py`, and the remaining command modules.
- [x] Classify each script as a reusable operation, command-specific payload builder, or trivial inline expression.
- [x] Use the Phase 1 and Phase 2 extractions to define the smallest proven packaging pattern.
- [x] Use `houdini_cli/remote/` for shared/domain script modules while retaining small command-adjacent scripts until their owning refactor.
- [x] Define stable, namespaced remote entrypoint names.
- [x] Define a consistent script-builder interface for arguments and result payloads.
- [x] Keep payload serialization structured; avoid ad hoc interpolation of user values.
- [x] Add focused unit tests for script builders and payload normalization.
- [x] Migrate parameter/HDA reference scanning as the reference implementation.
- [x] Smoke-test the reference implementation in live Houdini.
- [x] Document the chosen pattern for subsequent phases.
- [x] Record remaining scripts for incremental migration with their owning modules; avoid a single all-module rewrite.
- [x] Run the full test suite after the reference migration.

Exit criteria:

- [x] A tested remote-script pattern exists and later module splits can adopt it without inventing new execution conventions.

## Phase 4: Help Topic Split

Target module: `help.py` and new `help_topics/` modules.

- [x] Create `houdini_cli/commands/help_topics/` with a clear aggregation interface.
- [x] Move the `parm` help subtree into its own topic module.
- [x] Move the `hda` help subtree into its own topic module.
- [x] Move the `opencl` help subtree into its own topic module.
- [x] Move remaining command-group help subtrees into appropriately named topic modules.
- [x] Keep traversal, lookup, formatting, and `handle_help` orchestration in `help.py`.
- [x] Preserve help topic ordering and exact output unless an existing defect is separately documented.
- [x] Add a lightweight check that parser command names and top-level help topics remain synchronized.
- [x] Add coverage for unknown, group, nested, and leaf help paths.
- [x] Compare representative help output with the baseline.
- [x] Run the full test suite.

Exit criteria:

- [x] `help.py` owns help behavior while per-command modules own the static topic data.

## Phase 5: Node Command Split

Target module: `node.py` and new node command modules.

- [x] Create `houdini_cli/commands/node_references.py`.
- [x] Move reference payload collection and its remote script into `node_references.py`.
- [x] Reuse shared reference primitives from `parm_refs.py` where semantics match; keep node-specific payload assembly local.
- [x] Smoke-test node reference reporting against the selected HDA.
- [x] Create `houdini_cli/commands/node_lifecycle.py` for create, rename, copy, move, and delete behavior.
- [x] Create `houdini_cli/commands/node_nav.py` for network editor navigation.
- [x] Create `houdini_cli/commands/node_inspect.py` for get, errors, connections, and flags.
- [x] Keep parser registration and thin dispatch in `node.py`.
- [x] Preserve payload fields, command output, and node path semantics.
- [x] Add or update focused tests for each extracted responsibility.
- [x] Smoke-test each remote-backed node command group after extraction.
- [x] Run the full test suite.

Exit criteria:

- [x] `node.py` is a small command facade and each node workflow has a clear implementation owner.

## Phase 6: OpenCL Context Split

Target module: `opencl.py` and new OpenCL modules.

- [x] Create `houdini_cli/commands/opencl_bindings.py` for binding rows, value conversion, compact summaries, and hints.
- [x] Create `houdini_cli/commands/opencl_cop.py` for COP signatures, state, connection validation, and signature synchronization.
- [x] Create `houdini_cli/commands/opencl_sop.py` for SOP binding row validation and synchronization.
- [x] Create `houdini_cli/commands/opencl_dop.py` for Gas OpenCL DOP rows and synchronization.
- [x] Move the COP remote validation script using the Phase 3 remote-script pattern.
- [x] Keep parser registration plus sync/validate orchestration in `opencl.py`.
- [x] Make context dispatch explicit and exhaustive.
- [x] Preserve optional output normalization and generated spare behavior.
- [x] Add or update focused tests for bindings and each COP/SOP/DOP context.
- [x] Compare representative sync and validate output with the baseline.
- [x] Smoke-test COP, SOP, and DOP paths where suitable live nodes are available; record any unavailable context.
- [x] Run the OpenCL performance benchmarks and investigate any material regression.
- [x] Run the full test suite.

Exit criteria:

- [x] `opencl.py` is an orchestration facade and context-specific behavior no longer shares a monolithic implementation module.

## Phase 7: Remaining Parameter Command Split

Target module: `parm.py` and new parameter command modules.

- [ ] Create `houdini_cli/commands/parm_values.py` for get, full, menu, set, tuple, text, and full-set behavior.
- [ ] Create `houdini_cli/commands/parm_expressions.py` for expression get/set/clear and reference creation.
- [ ] Create `houdini_cli/commands/parm_templates.py` for template get/set, defaults, and definition-default remote behavior.
- [ ] Create `houdini_cli/commands/node_parms.py` for `node parms list/find` discovery.
- [ ] Adopt the Phase 3 remote-script pattern for extracted remote operations.
- [ ] Keep parser registration and thin dispatch in `parm.py`.
- [ ] Preserve scalar, tuple, multiparm, expression-language, raw-text, template, and definition-default semantics.
- [ ] Add or update focused tests for each extracted responsibility.
- [ ] Compare representative JSON and text output with the baseline.
- [ ] Smoke-test value, expression, template, default, and `node parms` workflows against the selected HDA.
- [ ] Run the parameter command performance benchmarks and investigate any material regression.
- [ ] Run the full test suite.

Exit criteria:

- [ ] `parm.py` is an orchestration facade and high-risk template/default mutation is isolated from routine value operations.

## Phase 8: Watchlist And Optional Refactors

These items are explicitly optional. Start one only when change pressure, duplication, testability, or further growth makes the boundary worthwhile.

### `hda_parms.py`

- [ ] Re-measure size, function count, and responsibility spread after Phases 1, 3, and 7.
- [ ] Decide whether HDA interface inspection, application, promotion, and defaults now warrant separate modules.
- [ ] If proceeding, extract one cohesive operation group at a time and preserve definition-editing/main-thread behavior.
- [ ] Add focused tests and live HDA smoke coverage for every extracted mutation path.

### `query.py`

- [ ] Reassess if traversal modes or performance-sensitive paths have grown.
- [ ] If proceeding, separate traversal/filtering from result summaries and remote payload collection.
- [ ] Run query performance benchmarks before and after any extraction.

### `attrib.py`

- [ ] Reassess responsibility spread and remote-script duplication.
- [ ] Split only if attribute discovery, reads, writes, or formatting develop independent change pressure.

### `session.py`

- [ ] Reassess responsibility spread and lifecycle complexity.
- [ ] Split only if session state, transport, or command orchestration cease to be cohesive.

### `recipe.py` And `recipe_common.py`

- [ ] Review their boundary together rather than treating file length alone as a problem.
- [ ] Consolidate or split only where recipe parsing, validation, execution, and shared helpers have demonstrably separate ownership.

### `shelf.py`

- [ ] Reassess responsibility spread and remote-script duplication.
- [ ] Split only if shelf discovery and mutation workflows grow independently.

### `hda_validate.py`

- [ ] Remove reference-audit helpers superseded by `parm_refs.py` in Phase 1.
- [ ] Reassess the remaining validators after shared remote infrastructure is established.
- [ ] Extract validator families only if the module remains difficult to review or extend.

Exit criteria:

- [ ] Every watchlist module has a recorded keep-as-is or refactor decision based on current evidence, not line count alone.

## Final Consolidation

- [ ] Remove obsolete compatibility imports, dead helpers, and superseded remote scripts.
- [ ] Check import direction for cycles and unclear ownership.
- [ ] Confirm parser registration remains discoverable and command groups remain complete.
- [ ] Confirm help topics cover the final parser command surface.
- [ ] Run static checks and formatting used by the repository.
- [ ] Run the complete performance benchmark suite and compare it with the Phase 0 baseline.
- [ ] Run the full automated test suite.
- [ ] Run the complete live Houdini smoke matrix against the test HDA.
- [ ] Update architecture or contributor documentation with the final module map and remote-script conventions.
- [ ] Re-run the production-code size/responsibility survey and record any remaining candidates.

Completion criteria:

- [ ] High-priority and medium-priority modules have clear ownership boundaries.
- [ ] Remote Houdini code follows one documented, tested pattern.
- [ ] Watchlist decisions are documented, including intentional non-refactors.
- [ ] CLI behavior, performance, and live Houdini workflows remain stable.
