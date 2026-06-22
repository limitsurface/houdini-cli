# Refactor Phase 3 Results

Date: 2026-06-21

Phase: cross-cutting remote script infrastructure

## Inventory

| Owner | Remote responsibility | Classification | Migration point |
| --- | --- | --- | --- |
| `parm_refs.py` | Parameter search, reference rows, HDA external audit | Shared domain module | Migrated in Phase 3 |
| `opencl.py` | Batched COP validation state | Command-specific inspection | Migrated in Phase 6 |
| `parm.py` | Definition default mutation; compact node parm rows | Main-thread mutation and command discovery | Parameter split, Phase 7 |
| `node_references.py` | Node reference payload | Command-specific inspection | Migrated in Phase 5 |
| `query.py` | Node traversal and neighbor rows | Reusable discovery | Query watchlist decision |
| `nodetype.py` | Bulk node-type discovery and detail reads | Reusable discovery | Migrate when nodetype changes next |
| `hda_inspect.py` | Definition and library discovery | Reusable discovery | Migrate when HDA inspection changes next |
| `hda_common.py` | HDA parameter tree | Small shared HDA inspection | HDA watchlist decision |
| `hda_parms.py` | Flat/folder reads; definition default mutation | HDA inspection and main-thread mutation | HDA parameter watchlist decision |
| `shelf.py` | Shelf/tool discovery | Reusable discovery | Shelf watchlist decision |
| `recipe_common.py` | Recipe discovery and tool application | Recipe domain module | Recipe boundary review |
| `recipe.py` | Recipe-owned application source | Dynamic domain source | Recipe boundary review |
| `eval.py` | User-supplied Python | Intentional public execution | Excluded |

No embedded remote execution was found in `attrib.py` or `session.py` at this phase.

## Reference Implementation

- Added `houdini_cli/remote/module.py` with `RemoteModule` and `python_literal`.
- Added `houdini_cli/remote/parm_refs.py` with three registered entrypoints.
- Moved the shared parameter/HDA reference source out of the command module.
- Replaced handwritten call-expression f-strings with registered aliases and centralized argument encoding.
- Added `docs/remote-script-conventions.md` for future migrations.

The abstraction deliberately does not cache installation, impose result schemas, or wrap user code. Those additions are not justified by the current command paths.

## Verification

- Remote infrastructure tests: four new tests covering structures, invalid values, install/evaluate, and unknown aliases
- Focused remote/reference tests: `25 passed`
- Full suite: `184 passed in 1.93s`
- Live `parm find`: `20` rows, truncated
- Live recursive `parm refs`: `100` rows, truncated
- Live HDA audit: `0` external, `0` absolute internal, `493` total references

Five-run focused medians after migration were `155.490 ms` for parameter search, `165.170 ms` for recursive references, and `547.380 ms` for HDA validation. An alternating five-run HDA audit comparison measured:

| Build | Minimum ms | Median ms | Mean ms | Maximum ms |
| --- | ---: | ---: | ---: | ---: |
| Installed pre-refactor CLI | 496.320 | 529.970 | 527.360 | 558.810 |
| Phase 3 source | 510.850 | 515.170 | 514.460 | 519.090 |

The remote module layer introduces no material performance regression.
