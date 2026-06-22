# Refactor Phase 5 Results

Date: 2026-06-21

Phase: node command split

## Result

- `node.py` now owns parser registration and handler dispatch only.
- Added `node_lifecycle.py` for create, rename, copy, move, and delete.
- Added `node_nav.py` for Network Editor navigation.
- Added `node_inspect.py` for get/set, messages, connections, and flags.
- Added `node_references.py` for local and remote reference payloads.
- Added `remote/node_references.py` using the Phase 3 `RemoteModule` convention.
- Reused `parm_refs.within_node_root` for matching local containment semantics.

Resulting module sizes:

| Module | Lines |
| --- | ---: |
| `node.py` | 136 |
| `node_lifecycle.py` | 108 |
| `node_nav.py` | 69 |
| `node_inspect.py` | 186 |
| `node_references.py` | 95 |

## Verification

- Focused node/parser tests after extraction: `24 passed`
- Focused node/debug/remote tests after shared containment: `26 passed`
- Final full suite: `186 passed in 2.02s`
- Compilation: successful
- Live target: `/obj/geo1/copnet1/ntsc_hou1`
- Focused get, errors, connections, flags, and no-frame navigation: successful
- All references: `0` parameter references and `98` input references
- External-only references: `0` parameter references and `1` input reference
- Full and external-only reference JSON: equivalent to installed pre-refactor CLI
- Lifecycle smoke: copied an internal OpenCL node to a temporary sibling and deleted it successfully

Alternating five-run node reference benchmark:

| Build | Median ms | Mean ms | Maximum ms |
| --- | ---: | ---: | ---: |
| Installed pre-refactor CLI | 173.320 | 176.620 | 194.530 |
| Phase 5 source | 170.180 | 173.350 | 190.400 |

The split and remote-module migration introduce no material performance regression.
