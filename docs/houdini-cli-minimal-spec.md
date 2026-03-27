# Houdini CLI Minimal Spec

## Intent

This CLI is for controlling a live Houdini session over `hrpyc`.

It is not a recipe tool.
The recipe system only matters here because SideFX introduced the useful `asData` / `setFromData` APIs alongside it.

The design goal is:

- keep the command surface small
- use Houdini's native data model where it actually helps
- avoid dozens of narrow verbs
- keep JSON I/O stable for agent use

## Architecture

### Process split

- Houdini runs normally
- Houdini exposes `hrpyc.start_server(...)`
- the CLI connects with `rpyc.classic.connect(...)`
- the CLI executes small Python handlers against the live `hou` session

### Internal layers

- `transport/rpyc.py`
  - connect/disconnect
  - get remote `hou`
  - retries/timeouts
- `commands/parm.py`
  - parameter inspection and updates
- `commands/node.py`
  - node inspection, creation, deletion, and wiring
- `commands/items.py`
  - optional graph snippet capture/apply
- `io/json.py`
  - input/output helpers

## Output Rules

### Default output

All machine-facing commands should return JSON.

Suggested top-level shape:

```json
{
  "ok": true,
  "data": {}
}
```

On failure:

```json
{
  "ok": false,
  "error": {
    "type": "hou.OperationFailed",
    "message": "..."
  }
}
```

### Human mode

Optional later feature:

- `--human` for concise summaries

But JSON should stay the default because the primary consumer is an agent.

## Tightened Command Surface

The earlier draft listed a deliberately conservative set of commands.
This section tightens that further by collapsing overlaps.

The guiding rules are:

- one command for discovery
- one command for focused inspection
- one command for structured read/write at each level
- keep `eval` as the only generic escape hatch

## 1. Session

### `houdini-cli ping`

Purpose:

- verify Houdini is reachable
- return version and hip path if possible

Implementation:

- connect
- call `hou.applicationVersionString()`
- call `hou.hipFile.path()`

### `houdini-cli eval`

Purpose:

- emergency escape hatch for arbitrary Python

Why it exists:

- prevents command explosion
- useful while the CLI surface is still small

Important:

- this should be explicitly treated as advanced/unsafe
- keep it separate from structured commands

Example:

```bash
houdini-cli eval --code "print(hou.node('/obj').children())"
```

## 2. Parm

This is the highest-value area for the data model.

### `houdini-cli parm get <parm-path>`

Uses:

- default: `hou.Parm.valueAsData()`
- expanded: `hou.Parm.asData()`

Purpose:

- default read path for parm inspection

Modes:

- default mode returns value data
- `--full` returns full parm data

### `houdini-cli parm set <parm-path> --json <payload>`

Uses:

- default: `hou.Parm.setValueFromData()`
- `--full`: `hou.Parm.setFromData()`

Purpose:

- default write path for parm mutation

Rationale:

- `parm get-value-data` and `parm get-data` are too similar
- `parm set-value-data` and `parm set-data` are too similar
- the distinction can be a mode flag instead of separate verbs

## 3. Node

### `houdini-cli node create <parent-path> <node-type> [--name <name>]`

Uses:

- `parent.createNode(...)`

Reason not to use `fromData` here:

- creation still needs a direct constructor path
- `asData` / `setFromData` are better after the node exists

### `houdini-cli node delete <node-path>`

Uses:

- `node.destroy()`

### `houdini-cli node get <node-path>`

Uses:

- default summary mode: focused inspection summary
- `--section parms`: `hou.OpNode.parmsAsData()`
- `--section inputs`: `hou.OpNode.inputsAsData()`
- `--section full`: `hou.OpNode.asData()`

Purpose:

- one read entrypoint for node inspection

Modes:

- default returns focused summary, not full data
- `--section parms` returns parameter data
- `--section inputs` returns wiring data
- `--section full` returns full node data

### `houdini-cli node set <node-path> --json <payload>`

Uses:

- `--section parms`: `hou.OpNode.setParmsFromData()`
- `--section inputs`: `hou.OpNode.setInputsFromData()`
- `--section full`: `hou.OpNode.setFromData()`

Purpose:

- one write entrypoint for structured node mutation

Warning:

- `--section full` is broader than the others
- `--section full` should require `--allow-structure-change`

## 4. Optional Item Commands

These are worth adding if you want compact graph snippet workflows.
They are not required for the first version.

### `houdini-cli items capture`

Uses:

- `hou.data.itemsAsData(...)`

Purpose:

- capture multiple nodes/dots/notes/boxes into one payload

### `houdini-cli items create`

Uses:

- `hou.data.createItemsFromData(...)`

Purpose:

- recreate a captured item set in a target network

## Commands To Avoid In V1

Do not add these as first-class commands unless a real workflow demands them:

- recipe save/apply/list/edit commands
- dozens of node-type-specific creation helpers
- special ramp commands
- special multiparm commands
- custom network box / sticky note CRUD commands
- schema-specific wrappers for every parameter type

Why:

- the data model already handles much of this
- the `eval` escape hatch covers edge cases
- overgrowth is exactly what you want to avoid

## Suggested First Release

Keep V1 to these commands:

- `ping`
- `eval`
- `parm get`
- `parm set`
- `node create`
- `node delete`
- `node get`
- `node set`

That is already enough to:

- inspect and modify parameter values
- handle ramps and multiparms through Houdini's own data APIs
- inspect and modify wiring
- snapshot and restore node state
- still fall back to arbitrary Python when needed

## Recommended Defaults And Flags

### Connection

- `--host`
- `--port`
- or env vars:
  - `HOUDINI_HOST`
  - `HOUDINI_PORT`

### Input handling

For payload commands support:

- `--json '{...}'`
- `--json-file payload.json`
- stdin when `--json -`

### Read modifiers

- `--brief`
- `--metadata`
- `--verbose`
- `--evaluate`
- `--children`
- `--editables`
- `--full`
- `--section parms|inputs|full`

### Write safety

For broad operations like `node set-data`:

- `--allow-structure-change`

This is useful as a guardrail so full-state apply is explicit.

## Method Mapping Summary

### Best default reads

- `parm get`: `hou.Parm.valueAsData()` by default, `hou.Parm.asData()` with `--full`
- `node get --section parms`: `hou.OpNode.parmsAsData()`
- `node get --section inputs`: `hou.OpNode.inputsAsData()`
- `node get --section full`: `hou.OpNode.asData()`

### Best default writes

- `parm set`: `hou.Parm.setValueFromData()` by default, `hou.Parm.setFromData()` with `--full`
- `node set --section parms`: `hou.OpNode.setParmsFromData()`
- `node set --section inputs`: `hou.OpNode.setInputsFromData()`
- `node set --section full`: `hou.OpNode.setFromData()`

## Recommendation

If we stay disciplined, the structured command surface can be reduced to:

- one escape hatch
- two parm commands
- four node commands
- optional item capture/apply later

That is enough power for an agent without recreating the bloat of the MCP server.
