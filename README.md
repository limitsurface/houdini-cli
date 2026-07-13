# houdini-cli

Agent-oriented CLI for controlling a live Houdini session over `hrpyc` / `rpyc`.
It provides a command-line alternative to Houdini MCP integrations.

## Overview

The CLI is built for structured scene interaction from agents and scripts. Current command areas include:

- connectivity checks: `ping`
- session state, scene saving, screenshots, viewport controls, and UI selection: `session`
- fallback execution: `eval`
- parameters, expressions, references, defaults, and template editing: `parm`
- node inspection, traversal, wiring, references, flags, copying, and reparenting: `node`
- digital asset inspection, creation, packaging, editing, and validation: `hda`
- shelf discovery and shelf tool CRUD: `shelf`
- attribute inspection: `attrib`
- cooked COP sampling: `cop`
- composed Solaris/USD stage summaries: `lop`
- OpenCL binding/signature validation and sync: `opencl`
- Python COP and Python Snippet SOP binding inspection, validation, and safe sync: `python`
- Attribute Wrangle creation and spare-parameter synchronization: `wrangle`
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

The bundled skill and local Houdini product docs are required for agents to use
the CLI and verify Houdini APIs and node behavior. The agent installing the CLI
should complete this setup:

1. Copy `skills/houdini-cli/` into the skill directory used by the agent
   harness. Use its harness-specific location when one exists; otherwise install
   it as `~/.agents/skills/houdini-cli/`.
2. In the installed skill, check whether `help_prepared/` already exists.
3. If it does not, ask the user to copy their local Houdini help folder into the
   installed skill's `help/` directory. The source usually matches an install
   path like `..\Houdini xx.x.xx\houdini\help`.
4. After the user confirms the copy is complete, run:

```powershell
python <installed-skill-path>/scripts/prepare_houdini_help.py
```

This builds a filtered searchable text corpus in
`<installed-skill-path>/help_prepared/` without modifying the copied help
source. Verify that the installed skill and prepared directory exist before
treating installation as complete.

After `help_prepared/` exists, the raw copied `<installed-skill-path>/help/`
folder is no longer needed.

## Quick Check

```powershell
houdini-cli ping
houdini-cli help
houdini-cli session selection
houdini-cli help hda
```

## Common Workflows

Execute multiline Python from a file or stdin:

```powershell
houdini-cli eval --input script.py
Get-Content script.py -Raw | houdini-cli eval --input -
```

```bash
cat script.py | houdini-cli eval --input -
```

Commands accepting `--input` consistently read UTF-8 files, or stdin when the
value is `-`. This applies to eval, multiline parameter values and expressions,
structured parameter data, shelf scripts, HDA interfaces, and HDA
sections/scripts.

Save the current scene or save it to a new path:

```powershell
houdini-cli session save
houdini-cli session save-as "D:/projects/example/scenes/test.hip"
houdini-cli session save-as "D:/projects/example/scenes/test.hip" --force
```

`session save-as` expands Houdini variables, creates missing parent directories,
and refuses to overwrite an existing file unless `--force` is supplied.

Inspect explicit node wiring:

```powershell
houdini-cli node connections /obj/geo1/null1
houdini-cli node get /obj/geo1/null1 --section inputs
houdini-cli node get /obj/geo1/null1 --section references --external-only
```

Survey and trace a large network without dumping every node or parameter:

```powershell
houdini-cli node summary /obj/asset --max-depth 1 --top-types 20
houdini-cli node find /obj/asset --type attribwrangle --max-results 40
houdini-cli node neighbors /obj/asset/OUT --direction upstream --depth 4
houdini-cli node parms list /stage/karmarendersettings --non-default --value-mode summary
houdini-cli node get /stage/karmarendersettings --section parms --parm engine --parm picture
```

Summarize the composed USD stage at a LOP output. Stage acquisition may cook;
the response reports cook counts, acquisition/traversal timings, traversal
bounds, and whether returned counts are complete.

```powershell
houdini-cli lop info /stage/karmarendersettings
houdini-cli lop info /stage/karmarendersettings --include-paths --max-prims 20000
```

Rename, copy, or reparent nodes:

```powershell
houdini-cli node rename /obj/geo1/box1 source_box
houdini-cli node copy /obj/geo1/box1 /obj/geo1/xform1 --parent /obj/geo2
houdini-cli node move /obj/geo1/box1 --parent /obj/geo2
houdini-cli node flags get /obj/geo2/box1
houdini-cli node flags set /obj/geo2/box1 --display true --render true
```

Read or edit parameter expressions and references:

```powershell
houdini-cli parm expression get /obj/geo1/box1/sizex
houdini-cli parm expression set /obj/geo1/box1/sizex --text 'ch("../sizey")'
houdini-cli parm reference /obj/geo1/box1/sizex /obj/geo1/box1/sizey
houdini-cli parm template get /obj/geo1/box1/sizex
```

After editing an OpenCL kernel:

```powershell
houdini-cli opencl validate /obj/geo1/work_here/opencl1
houdini-cli opencl sync /obj/geo1/work_here/opencl1
houdini-cli opencl sync /obj/geo1/work_here/opencl1 --bindings-only
houdini-cli opencl sync /obj/geo1/work_here/opencl1 --disconnect-invalid
```

Inspect and safely synchronize a Python COP from its `#bind` directives:

```powershell
houdini-cli python inspect /obj/copnet1/python1 --details
houdini-cli python sync /obj/copnet1/python1 --dry-run --details
houdini-cli python sync /obj/copnet1/python1 --prune-generated
```

Python COP sync preserves compatible spare values and expressions, retains custom
control folder placement, and reconnects inputs by port name after rebuilding.
The same commands support Python Snippet SOP binding rows and controls; classic
Python SOPs are intentionally excluded because they do not use the `#bind` model.

Capture a viewport screenshot:

```powershell
houdini-cli session screenshot --pane-name panetab1
houdini-cli session screenshot --index 0 --output "$HIP/houdini_cli/screenshots/view.png"
houdini-cli session viewport get
```

Screenshot and viewport responses include best-effort viewer context such as the
current network, display node, state, camera, and view type without changing the
viewer.

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

Inspect or validate an HDA:

```powershell
houdini-cli hda inspect /obj/geo1/my_asset --parms --sections --tools
houdini-cli hda validate /obj/geo1/my_asset --fresh-instance --cook --strict
houdini-cli hda section list /obj/geo1/my_asset
houdini-cli hda tool inspect /obj/geo1/my_asset
```

Package an existing plain subnet as an HDA:

```powershell
houdini-cli hda package /obj/geo1/my_subnet `
  --type-name Scy::my_asset::1.0 `
  --label "My Asset" `
  --library "C:/Users/Scy/Documents/houdini21.0/otls/my_asset.hda" `
  --min-inputs 1 `
  --max-inputs 1 `
  --tab-submenu "ScyTools/SOPs/" `
  --expanded-preview `
  --create-dirs
```

`hda package` currently packages an existing plain subnet. It applies the
requested definition metadata, can generate COP or SOP Tab-menu tools, and
validates a freshly instantiated asset by default. Use `houdini-cli help hda`
and `houdini-cli help hda <command>` for the complete lifecycle, interface,
section, script, and tool command surfaces.

Sample cooked COP output:

```powershell
houdini-cli cop sample /obj/fixes_here/copnet1/opencl1 --x 128 --y 128
```

Create a SOP Attribute Wrangle and generate spare parameters from its VEX (the
default kind remains `sop`):

```powershell
houdini-cli wrangle create /obj/work_here `
  --name grid_points `
  --run-over detail `
  --input grid.vfl `
  --create-spare-parms
```

LOP and DOP wrangles use the same command with `--kind lop`, `--kind
dop-geometry`, `--kind dop-pop`, or `--kind dop-gas-field`. Their specialized
parameters remain available through the regular `parm` commands.

Synchronize channel-call parameters on an existing wrangle:

```powershell
houdini-cli wrangle spare-parms sync /obj/work_here/grid_points
houdini-cli wrangle spare-parms sync /obj/work_here/grid_points --clear
```

Without `--clear`, compatible existing spare parameters are preserved. With
`--clear`, all spare parameters are deleted before Houdini recreates parameters
from the snippet's channel calls.

Search shelf tools and edit a shelf script:

```powershell
houdini-cli shelf find --query houCLI
houdini-cli shelf tools scy_Pipe
houdini-cli shelf tool get houCLI
houdini-cli shelf tool edit houCLI --input tool.py
```
