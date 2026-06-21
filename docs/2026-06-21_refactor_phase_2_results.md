# Refactor Phase 2 Results

Date: 2026-06-21

Phase: OpenCL spare parameter extraction

## Result

- Added `houdini_cli/commands/opencl_spares.py` as the owner of generated spare parameter templates and UI.
- Moved generated UI removal/rebuild, state capture/restore, scalar/vector binding filtering, and binding expression links.
- Retained COP/SOP/DOP context detection, signatures, binding rows, validation, and synchronization orchestration in `opencl.py`.
- Preserved the DOP-specific supported type set in `opencl.py` while sharing its expression setter and generated spare implementation.

Resulting production module sizes:

| Module | Lines |
| --- | ---: |
| `opencl.py` | 1,238 |
| `opencl_spares.py` | 234 |

## Verification

- Focused OpenCL tests: `17 passed`
- Full suite: `180 passed in 1.92s`
- Live source HDA: `/obj/geo1/copnet1/ntsc_hou1`
- Live test node: temporary copy of `rgb_to_yiq_ocl` under `/obj/geo1/copnet1`
- Sync with preservation: successful
- Validation after preserved sync: successful, COP context, two bindings
- Sync without preservation: successful
- Validation after default sync: successful, COP context, two bindings
- Cleanup: temporary node deleted successfully

An alternating seven-run comparison used the same live OpenCL node and session:

| Build | Minimum ms | Median ms | Mean ms | Maximum ms |
| --- | ---: | ---: | ---: | ---: |
| Installed pre-refactor CLI | 224.760 | 266.150 | 289.160 | 474.070 |
| Phase 2 source | 171.610 | 227.820 | 210.840 | 246.180 |

The extraction introduces no material performance regression.
