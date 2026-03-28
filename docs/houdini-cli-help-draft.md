# Houdini CLI Help Draft

## Purpose

Very short agent-facing command reference for the CLI as it exists now.

Use CLI help for command syntax.
Use local Houdini help files for Houdini documentation.

## Rules

- stdout is JSON
- prefer structured commands before `eval`
- prefer stdin for complex JSON payloads
- traversal is summary-first by default

## Commands

### `ping`

Check live Houdini connectivity.

Example:

```powershell
uv run houdini-cli ping
```

### `eval`

Run arbitrary Python in the live Houdini session with `hou` available.

Example:

```powershell
uv run houdini-cli eval --code "print(hou.applicationVersionString())"
```

### `parm get`

Get parameter data.

Default:

- value-oriented result

Full mode:

- `--full`

Examples:

```powershell
uv run houdini-cli parm get /obj/geo1/tx
```

```powershell
uv run houdini-cli parm get /obj/geo1/tx --full
```

### `parm set`

Set parameter data.

Default:

- scalar/simple write path

Full mode:

- `--full`

Examples:

```powershell
uv run houdini-cli parm set /obj/geo1/tx --json "3.0"
```

```powershell
'{"value":[1,2,3]}' | uv run houdini-cli parm set /obj/geo1/t --full --json -
```

### `node create`

Create a node under a parent path.

Example:

```powershell
uv run houdini-cli node create /obj geo --name test_geo
```

### `node delete`

Delete a node by path.

Example:

```powershell
uv run houdini-cli node delete /obj/test_geo
```

### `node get`

Focused node inspection by default.

Sections:

- `--section parms`
- `--section inputs`
- `--section full`

Examples:

```powershell
uv run houdini-cli node get /obj/geo1
```

```powershell
uv run houdini-cli node get /obj/geo1/null1 --section inputs
```

### `node set`

Apply structured node data.

Sections:

- `--section parms`
- `--section inputs`
- `--section full`

Example:

```powershell
'[{"from":"box1","from_index":0,"to_index":0}]' | uv run houdini-cli node set /obj/geo1/null1 --section inputs --json -
```

### `node list`

List nodes under a root with summary output.

Default limits:

- `max_nodes=50`
- `max_depth=1`

Example:

```powershell
uv run houdini-cli node list /obj/geo1
```

### `node find`

Find nodes under a root.

Example:

```powershell
uv run houdini-cli node find /obj/geo1 --type box
```

### `node summary`

Get a compact graph summary for a root.

Example:

```powershell
uv run houdini-cli node summary /obj/geo1
```

### `node inspect`

Get a focused summary for one node.

Example:

```powershell
uv run houdini-cli node inspect /obj/geo1/box1
```

### `node nav`

Navigate a Network Editor to one or more nodes in the same parent network.

Default:

- switch the pane to the shared parent network
- select the target nodes
- set the last node current
- frame the selection

Flags:

- `--no-frame`
- `--no-select`
- `--no-current`

Examples:

```powershell
uv run houdini-cli node nav /obj/geo1/box1 /obj/geo1/null1
```

```powershell
uv run houdini-cli node nav /obj/geo1/box1 --no-select --no-current
```

### `attrib list`

List cooked geometry attribute definitions on a node.

Optional filter:

- `--class point|prim|vertex|detail`

Example:

```powershell
uv run houdini-cli attrib list /obj/geo1/OUT
```

### `attrib get`

Inspect one cooked geometry attribute.

Required:

- attribute name
- `--class point|prim|vertex|detail`

Default:

- returns a capped sample
- includes truncation metadata

Narrowing:

- `--element N` for one explicit element

Optional numeric summaries:

- `--stats min,max,mean,median`

Examples:

```powershell
uv run houdini-cli attrib get /obj/geo1/OUT P --class point --element 0
```

```powershell
uv run houdini-cli attrib get /obj/geo1/OUT pscale --class point --limit 10 --stats min,max,mean
```

## Notes

- `rpyc 5.x` is required with the current Houdini/hrpyc pairing
- complex JSON should usually go through stdin with `--json -`
- component parm reads may return tuple-shaped data
- `node get --section parms` may return `null`
- `node nav` requires a graphical Houdini session with a Network Editor pane
- `attrib get` is summary-first by default and caps sampled values unless `--element` is used
- detail attributes do not accept `--element`
