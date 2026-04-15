# houdini-cli

Agent-oriented CLI for controlling a live Houdini session over `hrpyc` / `rpyc`.

## Overview

The CLI is built for structured scene interaction from agents and scripts. Current command areas include:

- connectivity checks: `ping`
- session state, screenshots, viewport controls, and UI selection: `session`
- fallback execution: `eval`
- parameters and compact node parm discovery: `parm`
- node inspection, traversal, wiring, and navigation: `node`
- shelf discovery and shelf tool CRUD: `shelf`
- attribute inspection: `attrib`
- cooked COP sampling: `cop`
- OpenCL binding/signature sync: `opencl`
- node type discovery: `nodetype`
- built-in structured help: `help`

The CLI talks to a running Houdini session through `hrpyc`, so Houdini must be open and serving before most commands will work.

## Install

Requires Python 3.12 or newer.

Recommended global install with `pipx`:

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
python -m pipx install git+https://github.com/limitsurface/houdini-cli.git
```

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

## Start Houdini Server

Create a Houdini shelf tool and paste in the Python from [shelf_script/start_hrpyc_server_shelf.py](./shelf_script/start_hrpyc_server_shelf.py). Run that shelf tool inside Houdini to start `hrpyc`.

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
houdini-cli session selection
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

Frame the current selection in the viewport and switch to an axis view:

```powershell
houdini-cli session viewport focus-selected
houdini-cli session viewport axis +x
houdini-cli session viewport set --t 8 6 10 --r 15 25 0 --pivot 2 3.5 4
```

Read the current Houdini node selection:

```powershell
houdini-cli session selection
```

Sample cooked COP output:

```powershell
houdini-cli cop sample /obj/fixes_here/copnet1/opencl1 --x 128 --y 128
```

Search shelf tools and edit a shelf script:

```powershell
houdini-cli shelf find --query houCLI
houdini-cli shelf tools scy_Pipe
houdini-cli shelf tool edit houCLI --input tool.py
```
