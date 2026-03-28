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
python -m pipx install .
```

After `ensurepath`, open a new terminal so the exposed `houdini-cli` command is available on `PATH`.

From a cloned GitHub repo, run the command from the repo root.

Direct install with `pip`:

```powershell
python -m pip install .
```

## Start Houdini Server

Use the shelf script at [shelf_script/start_hrpyc_server_shelf.py](./shelf_script/start_hrpyc_server_shelf.py) to start `hrpyc` inside Houdini.

## Local Houdini Docs

The repo-local skill at [skills/houdini-cli/SKILL.md](./skills/houdini-cli/SKILL.md) contains the local Houdini docs preparation flow, including how to prepare `help_prepared/` for raw `rg` lookup.

## Quick Check

```powershell
houdini-cli ping
houdini-cli help
```
