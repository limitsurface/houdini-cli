# Refactor Phase 8 Watchlist Reassessment

Date: 2026-06-22

Scope: optional refactor candidates from `2026-06-21_code_refactor_checklist.md` after Phases 1-7.

This phase is intentionally evidence-driven. The goal is to decide whether any remaining production module still has enough responsibility spread, remote-script duplication, or change pressure to justify another extraction now.

## Current Snapshot

| Module | Lines | Current Shape | Recommendation |
| --- | ---: | --- | --- |
| `hda_parms.py` | 555 | HDA interface inspection, folder discovery, layout application, promotion, and default mutation | Optional split next if HDA interface work continues |
| `query.py` | 456 | Node traversal, compact query rows, neighbor graph rows, and one remote discovery script | Keep behavior together; optionally migrate remote script only |
| `attrib.py` | 416 | Geometry attribute listing, summaries, topology histograms, and value reads | Keep as-is |
| `session.py` | 415 | Session save/frame/selection plus viewport screenshot/camera commands | Keep as-is until viewport work grows |
| `recipe.py` | 331 | Recipe parser, listing, apply commands, and create commands | Keep paired with `recipe_common.py`; optional remote packaging later |
| `recipe_common.py` | 318 | Recipe discovery payloads, recipe lookup, and tool recipe application helpers | Keep paired with `recipe.py`; optional remote packaging later |
| `shelf.py` | 316 | Shelf discovery and shelf tool mutation | Keep as-is; optionally migrate discovery remote script |
| `hda_validate.py` | 102 | Focused HDA validation facade using shared reference audit | Keep as-is |

## Findings

### `hda_parms.py`

This is the only remaining watchlist file with clear ownership spread after the earlier phases. It owns:

- read-only interface inspection: `inspect`, `folders`, `locate`;
- interface construction: template/folder spec parsing and `parms apply`;
- promotion: clone internal parameter templates and wire inner parameters to outer controls;
- definition default mutation: copy current instance values back into the definition.

The module also still contains three embedded Houdini-side scripts:

- flat HDA parameter rows;
- folder rows;
- defaults-from-current mutation.

The code is currently understandable, but the mutation paths are high-risk because they edit HDA definitions and call `matchCurrentDefinition()`/definition saves. A split is worthwhile only if HDA interface commands keep changing.

Recommended optional future split:

- `hda_parm_inspect.py` for `inspect`, `folders`, `locate`, flat rows, folder rows, and their remote payloads.
- `hda_parm_templates.py` for spec-to-template/folder construction and `parms apply`.
- `hda_parm_promote.py` for `parms promote`.
- `hda_parm_defaults.py` for `parms defaults` and the main-thread/default mutation remote payload.
- `houdini_cli/remote/hda_parms.py` for the three embedded scripts if this split proceeds.

Decision: optional later. Do not split immediately unless HDA interface work resumes.

### `query.py`

`query.py` is moderately large, but cohesive: it owns node traversal and compact query/neighbor output. The local and remote implementations are intentionally parallel because the remote path avoids broad RPyC traversal overhead.

The one obvious cleanup is mechanical: move `_QUERY_DISCOVERY_CODE` into `houdini_cli/remote/query.py` using `RemoteModule`. That would reduce inline script mass without changing command ownership.

Decision: keep as-is. Optional remote-script migration only.

### `attrib.py`

`attrib.py` is cohesive around cooked geometry attribute inspection. The handlers share geometry access, class mapping, attribute definition formatting, element sampling, and histogram helpers. There is no embedded remote script duplication, and splitting would likely create artificial boundaries around tightly related HOM geometry operations.

Decision: keep as-is.

### `session.py`

`session.py` has two clusters: basic session state (`ping`, save, frame, selection) and viewport/screenshot controls. The viewport cluster is longer, but still cohesive because the handlers share viewer resolution and camera payload helpers. There is no remote-script packaging problem.

A split into `session_viewport.py` could be justified if viewport commands grow, but it is not necessary now.

Decision: keep as-is.

### `recipe.py` And `recipe_common.py`

These should be treated as one boundary. `recipe.py` owns parser and user-facing apply/create commands; `recipe_common.py` owns shared discovery and tool-recipe helpers used by node type discovery. Their current split is meaningful.

There are still embedded remote code strings in both files. The useful next step would be remote packaging, not a command split:

- `houdini_cli/remote/recipes.py` for discovery, item lookup, and apply payloads.
- Potentially separate recipe creation helpers only if creation behavior expands or becomes harder to test.

Decision: keep current module pair. Optional remote-script migration later.

### `shelf.py`

`shelf.py` combines shelf discovery with shelf tool mutation. The file is not especially large and the mutation helpers are local to shelf behavior. The discovery remote script could move to `houdini_cli/remote/shelf.py`, but that is a packaging cleanup rather than a responsibility split.

Decision: keep as-is. Optional remote-script migration only.

### `hda_validate.py`

After Phase 1, `hda_validate.py` is small and focused. External reference auditing is delegated to `parm_refs.py`; the remaining module owns HDA validation orchestration, fresh-instance checks, frame cooking, warning/strict handling, and result shaping.

No obsolete reference-audit helpers remain.

Decision: keep as-is.

## Recommended Order If Phase 8 Continues

1. Optional: migrate remaining embedded remote scripts into `houdini_cli/remote/` without changing command ownership.
   - Start with `query.py`, because it has a single coherent discovery payload.
   - Then `shelf.py`.
   - Then `recipe_common.py`/`recipe.py`.
2. Optional: split `hda_parms.py` only when HDA interface work resumes.
   - Start with read-only inspection because it is lowest risk.
   - Move default mutation last because it edits definitions and depends on main-thread behavior.
3. Defer `attrib.py`, `session.py`, and `hda_validate.py`.

## Exit Decision

Phase 8 does not require immediate production refactors. The highest-value outcome is this recorded watchlist decision set, plus future optional remote-script packaging if the project wants to keep converging on the Phase 3 pattern.
