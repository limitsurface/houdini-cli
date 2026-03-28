# Houdini CLI `node nav` Spec

## Goal

Provide one UI-oriented navigation command that can:

- navigate a Network Editor to one or more nodes
- select those nodes
- optionally set the current node
- frame them in view

This is intended as the semantic counterpart to `computer_use`.

## Command Shape

```text
houdini-cli node nav <node-path> [<node-path> ...]
```

## Default Behavior

Given one or more node paths, the command should:

1. resolve all node paths
2. verify they exist
3. verify they share the same parent network
4. find a visible Network Editor pane
5. switch that pane to the common parent network
6. select the target nodes
7. set the last node as current
8. frame the selection

This should be opinionated.
The common use case is "show me this part of the network", not low-level pane choreography.

## Minimal Flags

Recommended initial flags:

- `--no-frame`
- `--no-select`
- `--no-current`

Default should remain:

- frame on
- select on
- set current on

## Constraints

### Same parent network

If multiple node paths are given, they should be required to share a common parent network.

If they do not:

- fail clearly
- do not guess

Reason:

- one Network Editor pane can only sensibly frame nodes in one visible network at a time

### Graphical Houdini session required

This command should fail clearly if:

- Houdini is not running with UI
- no Network Editor pane is available

## Output Shape

Example success payload:

```json
{
  "ok": true,
  "data": {
    "network": "/obj/geo1",
    "nodes": [
      "/obj/geo1/box1",
      "/obj/geo1/xform1"
    ],
    "selected": true,
    "current": "/obj/geo1/xform1",
    "framed": true
  }
}
```

Example failure payload:

```json
{
  "ok": false,
  "error": {
    "type": "ValueError",
    "message": "Nodes do not share the same parent network"
  }
}
```

## Implementation Notes

This likely belongs in the CLI as a node/UI bridge command, not in `computer_use`.

Likely Houdini-side actions:

- locate a `hou.NetworkEditor`
- `setPwd()` or equivalent to the target parent network
- update selection/current node
- call framing behavior on the pane

The exact HOM methods should be validated live before finalizing implementation.

## Why One Command Is Enough

These operations are tightly coupled in practice:

- navigate
- select
- current node
- frame

Splitting them into many commands would add complexity without much benefit.

## Relationship To `computer_use`

Recommended pattern:

- use `node nav` to semantically move Houdini to the right network region
- use `computer_use` to capture the actual UI afterward if visual confirmation is needed

This keeps:

- CLI responsible for Houdini semantics
- `computer_use` responsible for pixels
