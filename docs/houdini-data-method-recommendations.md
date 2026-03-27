# Houdini Data Method Recommendations

## Goal

Use Houdini's built-in data model APIs as the backbone of a smaller CLI, instead of reimplementing large amounts of custom serialization.

## Recommended Priority

### Tier 1: Essential

These should cover most agent workflows.

#### Parameters

- `hou.Parm.valueAsData()`
- `hou.Parm.setValueFromData()`
- `hou.Parm.asData()`
- `hou.Parm.setFromData()`

Why:

- value-only updates are common
- full parm state capture is still available when needed
- this replaces a lot of one-off type handling for ramps, expressions, locks, and multiparms

#### Nodes

- `hou.OpNode.parmsAsData()`
- `hou.OpNode.setParmsFromData()`
- `hou.OpNode.inputsAsData()`
- `hou.OpNode.setInputsFromData()`

Why:

- these let the CLI separate parameter edits from wiring edits
- they are narrower and safer than full `node.setFromData()`
- they are good building blocks for deterministic automation

### Tier 2: Structural

- `hou.OpNode.asData()`
- `hou.OpNode.setFromData()`
- `hou.OpNode.parmTemplatesAsData()`
- `hou.OpNode.appendParmTemplatesFromData()`
- `hou.OpNode.replaceParmTemplatesFromData()`

Why:

- needed for preset-like capture/apply
- useful for subnet contents, spare parms, and richer reconstruction
- should be exposed carefully because they can change a lot of state at once

### Tier 3: Graph Snippets

- `hou.data.itemsAsData()`
- `hou.data.createItemsFromData()`
- `hou.data.clusterItemsAsData()`
- `hou.data.createClusterItemsFromData()`

Why:

- ideal for copying/pasting a node snippet
- good for recipe-like reusable graph fragments
- potentially enough to replace many "create N nodes and wire them up" commands

## Suggested CLI Shape

### Parameters

- `parm get-value-data <parm-path>`
- `parm set-value-data <parm-path> --json <payload>`
- `parm get-data <parm-path>`
- `parm set-data <parm-path> --json <payload>`

### Node Parameters

- `node get-parms-data <node-path>`
- `node set-parms-data <node-path> --json <payload>`

### Wiring

- `node get-inputs-data <node-path>`
- `node set-inputs-data <node-path> --json <payload>`

### Full Node State

- `node get-data <node-path>`
- `node set-data <node-path> --json <payload>`

### Item Capture / Replay

- `items capture --parent <node-path> --selected`
- `items create --parent <node-path> --json <payload>`
- `cluster capture --target <node-path> --selected`
- `cluster create --parent <node-path> --target <node-path> --json <payload>`

## Design Guidance

### Prefer narrow inverse methods

Use:

- `setValueFromData()` when only the value should change
- `setParmsFromData()` when only node parameters should change
- `setInputsFromData()` when only wires should change

Avoid using `setFromData()` as the default write path. It is more of a "reconcile this object with serialized state" tool.

### Be careful with brief mode

The docs indicate that brief mode can collapse certain dicts down to scalars or lists.

That means:

- good for human readability
- less good for stable schemas

Recommendation:

- machine mode: `brief=False`
- human mode: optional `--brief`

### Be careful with evaluated values

The docs distinguish:

- raw captured values, including expressions/keyframes
- evaluated values at the current time

Recommendation:

- default to non-evaluated when capture is meant to be replayable
- add an explicit `--evaluate` flag for inspection-oriented workflows

### Treat parm templates as advanced

Spare parm recreation is useful, but parameter interface mutation is a bigger hammer than ordinary parm edits.

Recommendation:

- keep parm template commands separate
- do not couple them to ordinary node get/set by default

## Why This Beats The Current MCP Shape

The cloned MCP implementation mainly hand-builds small operation-specific wrappers around `hou`.

The data-model-first approach should reduce:

- custom response schemas
- custom wiring serialization
- special-case ramp and multiparm handling
- lots of narrow tools whose only purpose is to move small dicts around

It also gives you a more future-proof interface because it leans on SideFX's own serialization layer instead of reverse-engineering one.

## Best First Prototype

If only a minimal first cut is needed, start with:

1. `parm get-value-data`
2. `parm set-value-data`
3. `node get-parms-data`
4. `node set-parms-data`
5. `node get-inputs-data`
6. `node set-inputs-data`
7. `node get-data`
8. `node set-data`

That is already enough to cover:

- inspect parameter state
- edit values
- inspect and recreate wiring
- capture and reapply whole-node state

It is a far smaller and cleaner base than a large MCP tool catalog.
