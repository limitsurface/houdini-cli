# houdini-cli

Agent-oriented CLI for controlling a live Houdini session over `hrpyc` / `rpyc`.

## Overview

The CLI is built for structured scene interaction from agents and scripts. Current command areas include:

- session checks: `ping`
- fallback execution: `eval`
- parameters: `parm`
- node inspection and editing: `node`
- attribute inspection: `attrib`
- node type discovery: `nodetype`
- built-in structured help: `help`

The CLI talks to a running Houdini session through `hrpyc`, so Houdini must be open and serving before most commands will work.

## Install

Recommended global install with `pipx`:

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
python -m pipx install git+https://github.com/limitsurface/houdini-cli.git
```

For this private repo, make sure your GitHub credentials are available to git before installing from the repo URL.

From a local clone instead:

```powershell
python -m pipx install .
```

To refresh an existing `pipx` install from a local clone after pulling changes:

```powershell
python -m pipx install --force .
```

Direct install with `pip`:

```powershell
python -m pip install .
```

## Releases

Pushing a tag like `v0.1.0` triggers a GitHub Actions workflow that:

- runs the test suite
- builds the wheel and sdist
- creates a GitHub Release with the built artifacts attached

## Start Houdini Server

Use the shelf script at [shelf_script/start_hrpyc_server_shelf.py](./shelf_script/start_hrpyc_server_shelf.py) to start `hrpyc` inside Houdini.

## Local Houdini Docs

If you want repo-local Houdini product docs for raw `rg` lookup:

1. Check whether `skills/houdini-cli/help_prepared/` already exists.
2. If it does not, copy your local Houdini help folder into `skills/houdini-cli/help/`.
   The source usually matches an install path like `..\Houdini xx.x.xx\houdini\help`.
3. Run:

```powershell
python skills/houdini-cli/scripts/prepare_houdini_help.py
```

This builds a filtered searchable text corpus in `skills/houdini-cli/help_prepared/` without modifying the copied help source.

After `help_prepared/` exists, the raw copied `skills/houdini-cli/help/` folder is no longer needed.

## Quick Check

```powershell
houdini-cli ping
houdini-cli help
```

## Common Workflows

Inspect explicit node wiring:

```powershell
houdini-cli node connections /obj/geo1/null1
houdini-cli node get /obj/geo1/null1 --section inputs
```

After editing an OpenCL kernel:

```powershell
houdini-cli opencl sync /obj/geo1/work_here/opencl1
houdini-cli opencl sync /obj/geo1/work_here/opencl1 --bindings-only
```

Capture a viewport screenshot:

```powershell
houdini-cli session screenshot --pane-name panetab1
houdini-cli session screenshot --index 0 --output "$HIP/houdini_cli/screenshots/view.png"
```

Sample cooked COP output:

```powershell
houdini-cli cop sample /obj/fixes_here/copnet1/opencl1 --x 128 --y 128
```
