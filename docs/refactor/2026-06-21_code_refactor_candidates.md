# Code Refactor Candidates

Date: 2026-06-21

Scope: production code under `houdini_cli/` only. Tests were intentionally excluded.

## Summary

The strongest refactor candidates are `houdini_cli/commands/opencl.py`, `houdini_cli/commands/parm.py`, and `houdini_cli/commands/help.py`.

These files are not just long. They combine parser registration, local fallback behavior, remote Houdini scripts, normalization helpers, and command handlers in the same module. That makes changes harder to review and increases the chance that a focused bug fix touches unrelated command surfaces.

## Highest Priority

### `houdini_cli/commands/opencl.py`

Current shape:

- About 1.4k lines.
- Roughly 58 functions.
- Covers COP signatures, SOP binding rows, Gas OpenCL DOP rows, generated spare parameters, validation summaries, connection validation, remote Houdini state collection, and CLI handlers.
- Contains a large embedded Houdini-side Python script for COP validation state.

Why it is a refactor candidate:

- It has at least three domain modes in one file: COP, SOP, and DOP.
- Binding extraction, desired-state modeling, current-state introspection, sync application, and result formatting are interleaved.
- The embedded remote script duplicates logic from local helpers, so fixes can easily land in one side only.
- Recent work on spare parameter preservation and output optional normalization had to move through several unrelated sections of the file.

Suggested split:

- `opencl.py`: parser registration plus `handle_sync` and `handle_validate` orchestration only.
- `opencl_bindings.py`: binding row/value conversion, compact binding summaries, binding hints.
- `opencl_spares.py`: generated spare parm UI, capture/restore, value-link expressions.
- `opencl_cop.py`: COP signature entries, current state, input connection validation, sync signature.
- `opencl_sop.py`: SOP row validation and sync behavior.
- `opencl_dop.py`: Gas OpenCL DOP parameter rows and sync behavior.
- `remote_scripts/opencl_cop.py` or similar: Houdini-side script strings or a helper that builds them.

Low-risk first step:

Move spare-parameter helpers into `opencl_spares.py` and import them from `opencl.py`. This is cohesive, well covered by tests, and mostly independent of COP/SOP/DOP branching.

### `houdini_cli/commands/parm.py`

Current shape:

- About 1.2k lines.
- Roughly 56 functions.
- Registers the top-level `parm` group and the nested `node parms` group.
- Covers scalar reads/writes, tuple writes, text/full JSON writes, expressions, references, search, recursive refs, template inspection/patching, definition defaults, and compact node parm discovery.
- Contains multiple embedded Houdini-side scripts.

Why it is a refactor candidate:

- It mixes several user workflows that have different risk profiles. Simple value reads live beside definition-level template mutation and remote main-thread default editing.
- Parameter reference/search helpers now overlap conceptually with HDA validation reference scanning.
- `register_parser` is large because every subcommand is registered inline.
- Remote script blocks are hard to diff and test in isolation.

Suggested split:

- `parm.py`: parser registration and thin handler dispatch.
- `parm_values.py`: get/full/menu/set/tuple/text/full-set behavior.
- `parm_expressions.py`: expression get/set/clear and reference creation.
- `parm_refs.py`: find/refs, channel reference parsing, root/external classification.
- `parm_templates.py`: template get/set/default logic and definition default remote helper.
- `node_parms.py`: `node parms list/find` compact discovery.

Low-risk first step:

Extract `find` and `refs` into `parm_refs.py`, then have both `parm.py` and `hda_validate.py` share the same channel-reference resolver. This directly reduces duplication introduced by the HDA audit work.

## Medium Priority

### `houdini_cli/commands/help.py`

Current shape:

- About 800 lines.
- Almost entirely a static `HELP_TREE` data structure plus a small traversal API.

Why it is a refactor candidate:

- The file is easy to understand but hard to review because unrelated help edits are close together in one large literal.
- It duplicates command surface details that also exist in parser registration.
- Merge conflicts will become more likely as command groups grow.

Suggested split:

- Keep traversal and `handle_help` in `help.py`.
- Move command-group data into `help_topics/` modules such as `parm.py`, `node.py`, `hda.py`, `opencl.py`.
- Optionally add a lightweight check that parser-level command names and help topics stay in sync.

Low-risk first step:

Move only the `opencl`, `parm`, and `hda` help subtrees into separate modules. Those are the areas seeing the most frequent CLI surface changes.

### `houdini_cli/commands/node.py`

Current shape:

- About 600 lines.
- Roughly 24 functions.
- Handles node creation, rename/copy/move/delete, nav, get/set, references, errors, connections, and flags.
- Contains a remote script block for reference payload collection.

Why it is a refactor candidate:

- It is smaller than `opencl.py` and `parm.py`, but it has several unrelated responsibilities.
- Reference scanning overlaps with `parm refs` and HDA validation concepts.
- `node get` payload assembly is a broad surface that can grow quickly.

Suggested split:

- `node.py`: parser and handler dispatch.
- `node_lifecycle.py`: create/rename/copy/move/delete.
- `node_nav.py`: network editor navigation.
- `node_inspect.py`: get/errors/connections/flags.
- `node_references.py`: reference payload and remote script.

Low-risk first step:

Extract `node_references.py`; it has a clear boundary and natural future sharing with `parm_refs.py`.

## Watchlist

These files are sizable but not immediate refactor targets:

- `houdini_cli/commands/hda_parms.py`: about 550 lines, but the scope is focused on HDA interface operations.
- `houdini_cli/commands/query.py`: about 450 lines, likely acceptable unless more traversal/performance paths accumulate.
- `houdini_cli/commands/attrib.py`, `session.py`, `recipe.py`, `recipe_common.py`, `shelf.py`: mid-sized and mostly cohesive today.
- `houdini_cli/commands/hda_validate.py`: grew with external reference auditing. It should shrink if the shared `parm_refs.py` extraction happens.

## Cross-Cutting Opportunity

Several modules embed Houdini-side Python scripts as raw strings near local fallback logic. This appears in `opencl.py`, `parm.py`, `hda_validate.py`, `node.py`, and other command modules.

Possible direction:

- Introduce a small `houdini_cli/remote/` package for remote script snippets or script builders.
- Keep remote entrypoint names stable and namespaced.
- Add unit tests around the Python-side builders and focused live smoke tests around the remote entrypoints.

This would make future Houdini-main-thread fixes easier to review, but it should follow one concrete extraction first so the pattern is proven rather than invented broadly.

## Suggested Order

1. Extract `parm_refs.py` and reuse it from `hda_validate.py`.
2. Extract OpenCL spare-parameter helpers into `opencl_spares.py`.
3. Establish cross-cutting remote-script infrastructure from the patterns proven by the first two extractions.
4. Split `help.py` into per-command help topic modules.
5. Extract `node_references.py`, then split the remaining node responsibilities if the boundary holds.
6. Revisit OpenCL COP/SOP/DOP splitting after the spare helper extraction proves stable.
7. Split the remaining parameter workflows after the shared reference and remote-script patterns are settled.
8. Reassess every watchlist module and refactor only where current evidence supports it.

The executable phase plan and acceptance gates are tracked in `2026-06-21_code_refactor_checklist.md`.
