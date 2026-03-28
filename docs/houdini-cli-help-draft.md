# Houdini CLI Help Draft

## Purpose

Compact agent-facing command reference.
Focus on command shape, not tutorial detail.
Use local Houdini help files for Houdini documentation.

## Rules

- stdout is JSON
- prefer structured commands before `eval`
- prefer stdin for complex JSON payloads
- traversal is summary-first by default

## Commands

### `ping`

```powershell
uv run houdini-cli ping
```

### `eval`

```powershell
uv run houdini-cli eval --code "print(hou.applicationVersionString())"
```

### `parm get`

Syntax:

```powershell
uv run houdini-cli parm get <parm-path> [--full]
```

Example:

```powershell
uv run houdini-cli parm get /obj/cli_attrib_live/box1/sizex
```

### `parm set`

Syntax:

```powershell
uv run houdini-cli parm set <parm-path> --json <payload-or-'-'> [--full]
```

Examples:

```powershell
uv run houdini-cli parm set /obj/cli_attrib_live/box1/sizex --json "2.5"
```

```powershell
'{"value":[1,2,3]}' | uv run houdini-cli parm set /obj/cli_attrib_live/box1/t --full --json -
```

### `node create`

Syntax:

```powershell
uv run houdini-cli node create <parent-path> <node-type> [--name <node-name>]
```

### `node delete`

```powershell
uv run houdini-cli node delete <node-path>
```

### `node get`

Syntax:

```powershell
uv run houdini-cli node get <node-path> [--section parms|inputs|full]
```

Examples:

```powershell
uv run houdini-cli node get /obj/cli_attrib_live/OUT --section inputs
```

### `node set`

Syntax:

```powershell
uv run houdini-cli node set <node-path> --section parms|inputs|full --json <payload-or-'-'>
```

### `node list`

Syntax:

```powershell
uv run houdini-cli node list <root-path> [--max-depth N] [--max-nodes N]
```

### `node find`

Syntax:

```powershell
uv run houdini-cli node find <root-path> [--type TYPE] [--category CATEGORY] [--name TEXT]
```

### `node summary`

```powershell
uv run houdini-cli node summary <root-path> [--max-depth N] [--max-nodes N]
```

### `node inspect`

```powershell
uv run houdini-cli node inspect <node-path>
```

### `node nav`

Syntax:

```powershell
uv run houdini-cli node nav <node-path> [<node-path> ...] [--no-frame] [--no-select] [--no-current]
```

Requires shared parent network and graphical Houdini UI.

### `attrib list`

Syntax:

```powershell
uv run houdini-cli attrib list <node-path> [--class point|prim|vertex|detail]
```

### `attrib get`

Syntax:

```powershell
uv run houdini-cli attrib get <node-path> <attrib-name> --class point|prim|vertex|detail [--element N] [--limit N]
```

### `nodetype list`

Syntax:

```powershell
uv run houdini-cli nodetype list --category obj|sop|cop|vop|rop|lop|dop|shop [--limit N]
```

### `nodetype find`

Syntax:

```powershell
uv run houdini-cli nodetype find --category obj|sop|cop|vop|rop|lop|dop|shop (--query TEXT | --prefix TEXT) [--limit N]
```

### `nodetype get`

```powershell
uv run houdini-cli nodetype get --category obj|sop|cop|vop|rop|lop|dop|shop <type-key>
```

## Notes

- `rpyc 5.x` is required with the current Houdini/hrpyc pairing
- complex JSON should usually go through stdin with `--json -`
- component parm reads may return tuple-shaped data
- `node get --section parms` may return `null`
- `attrib get` is summary-first by default and caps sampled values unless `--element` is used
- aggregate attribute stats are intentionally out of scope for now; use SOP/VEX-side analysis when needed
- detail attributes do not accept `--element`
- `nodetype list` and `nodetype find` are intentionally compact and capped by default
