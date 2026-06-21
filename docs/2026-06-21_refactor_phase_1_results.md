# Refactor Phase 1 Results

Date: 2026-06-21

Phase: shared parameter reference logic

## Result

- Added `houdini_cli/commands/parm_refs.py` as the owner of local and remote parameter search/reference scanning.
- `parm.py` retains parser registration, result envelopes, and thin `find`/`refs` handlers.
- `hda_validate.py` retains validation orchestration and delegates its reference audit.
- Removed the duplicate local resolvers and both duplicate embedded remote scripts.
- Preserved the distinction between direct parameter HOM references and the tuple-aware HDA audit.

Resulting production module sizes:

| Module | Lines |
| --- | ---: |
| `parm.py` | 890 |
| `parm_refs.py` | 588 |
| `hda_validate.py` | 102 |

`parm_refs.py` is intentionally cohesive but still includes the shared Houdini-side script. Phase 3 will decide how remote scripts are packaged; this phase does not pre-empt that decision.

## Verification

- Focused tests: `21 passed`
- Final full suite: `180 passed in 2.00s`
- Live HDA: `/obj/geo1/copnet1/ntsc_hou1`
- `parm find`: `20` rows, truncated, same representative first row
- recursive `parm refs`: `100` rows, truncated, `0` external references in the sample
- HDA audit: `0` external, `0` absolute internal, `493` total references

Post-extraction benchmark, three iterations per probe:

| Probe | Baseline median ms | Phase 1 median ms | Change |
| --- | ---: | ---: | ---: |
| Parameter search | 146.017 | 153.519 | +5.1% |
| Recursive parameter references | 160.832 | 161.039 | +0.1% |
| HDA external-reference validation | 480.501 | 501.545 | +4.4% |

All `23` probes and `69` runs passed with no suite concerns. These differences are small relative to independent CLI process and live-session timing variation and do not indicate a material regression.
