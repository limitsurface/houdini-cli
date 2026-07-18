# houdini-cli

Agent-oriented CLI for controlling a live Houdini session over `hrpyc` / `rpyc`.
It provides a command-line alternative to Houdini MCP integrations.

## Overview

The CLI gives agents and scripts structured tools for inspecting and editing
Houdini scenes, including nodes, parameters, assets, shelves, viewports, USD,
Copernicus, wrangles, and OpenCL. Built-in help provides the complete command
reference.

Most commands require an open Houdini session serving through `hrpyc`.

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
the CLI and verify Houdini APIs and node behavior.

The agent installing the CLI should complete this setup:

1. Copy `skills/houdini-cli/` into the skill directory used by the agent
   harness. Use its harness-specific location when one exists; otherwise install
   it as `~/.agents/skills/houdini-cli/`.
2. In the installed skill, check whether `help_prepared/` already exists.
3. Locate the user's Houdini help directory. It usually matches an installation
   path such as `..\Houdini xx.x.xx\houdini\help`.
4. Prepare it directly from that installation path:

```powershell
python <installed-skill-path>/scripts/prepare_houdini_help.py `
  --source "C:\Program Files\Side Effects Software\Houdini xx.x.xxx\houdini\help"
```

This builds a filtered searchable text corpus in
`<installed-skill-path>/help_prepared/` without modifying the Houdini
installation. Verify that the installed skill and prepared directory exist
before treating installation as complete.

As an offline alternative, copy the Houdini help directory to
`<installed-skill-path>/help/` and omit `--source`. After `help_prepared/`
exists, that raw copied folder is no longer needed.

## Quick Check

```powershell
houdini-cli ping
houdini-cli help
houdini-cli session selection
houdini-cli help hda
```
