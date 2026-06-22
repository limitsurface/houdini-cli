# Refactor Phase 7 Results

Date: 2026-06-22

Phase: Remaining parameter command split.

## Summary

- Reduced `houdini_cli/commands/parm.py` to parser registration and handler imports.
- Added `houdini_cli/commands/parm_common.py` for shared parameter lookup, tuple, component, and CLI value parsing helpers.
- Added `houdini_cli/commands/parm_values.py` for value reads and writes.
- Added `houdini_cli/commands/parm_expressions.py` for expression and reference commands.
- Added `houdini_cli/commands/parm_templates.py` for template inspection, template patching, and default mutation.
- Added `houdini_cli/commands/node_parms.py` for `node parms list/find`.
- Moved the definition-default remote edit into `houdini_cli/remote/parm_templates.py`.
- Moved the remote node-parameter row collector into `houdini_cli/remote/node_parms.py`.
- Added handler wrappers for `parm find` and `parm refs` to `parm_refs.py`, so parameter-reference command behavior remains owned by the Phase 1 module.

## Verification

- Focused tests: `.venv\Scripts\python.exe -m pytest tests/test_parm.py tests/test_remote.py -p no:cacheprovider --basetemp D:\vibe_code\00_houdini_projects\houdini_CLI\.tmp_pytest`
  - Result: 26 passed.
- Full suite: `.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp D:\vibe_code\00_houdini_projects\houdini_CLI\.tmp_pytest`
  - Result: 189 passed.
- Live smoke:
  - Copied `/obj/geo1/copnet1/ntsc_hou1/rgb_to_yiq_ocl` to `/obj/geo1/copnet1/rgb_to_yiq_ocl1`.
  - Verified `parm get`, `parm full`, `parm set`, `parm expression get/set/clear`, `parm reference`, `parm template get`, `parm default set --target instance --current`, and `node parms find`.
  - Deleted `/obj/geo1/copnet1/rgb_to_yiq_ocl1` after smoke testing.
  - `parm template get` on `/input1_optional` failed because the template is stored under a tuple template name that is not itself a valid parameter path; `kernelcode` was used for the template/default smoke because it is a real single parameter.
- Performance A/B over 5 runs:
  - `parm get kernelcode`: installed median 245.303 ms, source median 224.735 ms.
  - `node parms find input`: installed median 219.833 ms, source median 218.461 ms.
  - `parm find references`: installed median 218.925 ms, source median 228.056 ms.
  - `parm refs recursive`: installed median 214.616 ms, source median 240.743 ms.
  - No material regression was observed; the slower reference run remains within the normal live Houdini RPC variance seen during this survey.

## Deferred

- No command syntax, output contract, or mutation behavior changes were intentionally introduced.
