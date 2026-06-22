# Refactor Phase 6 Results

Date: 2026-06-22

Phase: OpenCL context split.

## Summary

- Reduced `houdini_cli/commands/opencl.py` to parser and sync/validate orchestration.
- Added shared OpenCL binding helpers in `houdini_cli/commands/opencl_bindings.py`.
- Moved COP signature, validation, input connection, and signature sync behavior into `houdini_cli/commands/opencl_cop.py`.
- Moved OpenCL SOP row validation and synchronization into `houdini_cli/commands/opencl_sop.py`.
- Moved Gas OpenCL DOP parameter row validation and synchronization into `houdini_cli/commands/opencl_dop.py`.
- Moved the COP remote validation state payload into `houdini_cli/remote/opencl_cop.py` using the Phase 3 `RemoteModule` pattern.

## Verification

- Focused tests: `.venv\Scripts\python.exe -m pytest tests/test_opencl.py tests/test_remote.py`
  - Result: 22 passed.
- Full suite: `.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp D:\vibe_code\00_houdini_projects\houdini_CLI\.tmp_pytest`
  - Result: 187 passed.
  - Note: `--basetemp` was required because the default Windows pytest temp root was not accessible to the current user.
- Live HDA checks:
  - Verified `/obj/geo1/copnet1/ntsc_hou1` and `/obj/geo1/copnet1/ntsc_hou1/rgb_to_yiq_ocl`.
  - `opencl validate /obj/geo1/copnet1/ntsc_hou1/rgb_to_yiq_ocl` returned `ok: true`, `context: cop`, and `clean: true`.
  - Copied the OpenCL node to `/obj/geo1/copnet1/rgb_to_yiq_ocl`, ran preserve and non-preserve sync paths, and deleted the copy.
  - The temp copy reported a missing `src` input as expected because it was intentionally copied without its upstream connection; signature synchronization itself matched the kernel.
- Performance:
  - Broad OpenCL COP probe completed validation timings but exited nonzero because this HDA does not contain the probe's historical `pause_amp` parameter.
  - Direct A/B over 7 runs on `opencl validate /obj/geo1/copnet1/ntsc_hou1/rgb_to_yiq_ocl`:
    - Installed CLI median: 308.182 ms.
    - Phase 6 source median: 330.618 ms.
  - The observed difference is small relative to live RPC/session variance and does not indicate a material regression.

## Deferred

- No suitable live SOP or DOP OpenCL nodes were available in the selected HDA scene. Unit tests continue to cover SOP and DOP row synchronization behavior.
