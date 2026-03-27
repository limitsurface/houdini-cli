# Houdini CLI Traversal Spec

## Goal

Traversal exists to answer:

- what is in this network
- how large it is
- where the important nodes are
- what should be inspected next

Traversal does not exist to dump full node state into context.

The design goal is:

- support very large networks safely
- keep default payloads small
- make truncation explicit
- separate discovery from deep inspection

## Core Principle

Traversal should be:

- imperative internally
- summary-first externally

That means:

- use ordinary HOM traversal to walk the graph
- filter and aggregate inside Houdini
- return compact summaries by default
- only call `asData()` or `parmsAsData()` after narrowing to a small set of nodes

## Traversal Layers

## 1. Structural Summary

This is the default output for traversal commands.

Per node, return only:

- `path`
- `name`
- `type`
- `category`
- `child_count`
- `input_count`
- `output_count`
- optional core flags when relevant

Do not return:

- all parms
- all children recursively
- full `asData()` payloads
- large per-node metadata blobs

Example:

```json
{
  "path": "/obj/geo1/noise1",
  "name": "noise1",
  "type": "attribnoise",
  "category": "Sop",
  "child_count": 0,
  "input_count": 1,
  "output_count": 1
}
```

## 2. Focused Summary

This is for a narrowed subset of nodes.

It may include:

- input connection summaries
- output connection summaries
- non-default parm names
- expression/keyframe indicators
- error/warning counts
- display/render/bypass state

It still should not return full serialized node state unless explicitly requested.

Example:

```json
{
  "path": "/obj/geo1/noise1",
  "type": "attribnoise",
  "inputs": [
    {
      "from": "/obj/geo1/grid1",
      "to_index": 0
    }
  ],
  "interesting_parms": [
    "offset",
    "amp",
    "elementsize"
  ],
  "has_expressions": false,
  "warning_count": 0,
  "error_count": 0
}
```

## 3. Full Structured Data

This is only for explicit requests against one node or a very small set of nodes.

Use:

- `hou.Parm.asData()`
- `hou.OpNode.parmsAsData()`
- `hou.OpNode.inputsAsData()`
- `hou.OpNode.asData()`

This should not be part of broad traversal.

## Traversal Commands

The traversal surface should be small and composable.

## `node list`

Lists immediate children or a bounded recursive view.

Example:

```bash
houdini-cli node list /obj/geo1 --max-depth 1
```

Default behavior:

- shallow by default
- summary output only

Useful filters:

- `--type`
- `--category`
- `--name`
- `--max-depth`
- `--max-nodes`

## `node find`

Searches under a root for nodes matching a filter.

Example:

```bash
houdini-cli node find /obj/geo1 --type attribwrangle
```

Supported filters:

- `--type`
- `--category`
- `--name`
- `--path-pattern`
- `--has-errors`
- `--has-warnings`

Default behavior:

- returns structural summaries only

## `node tree`

Returns a bounded tree-oriented summary.

This is useful when the user wants shape, not detail.

Example:

```bash
houdini-cli node tree /obj/geo1 --max-depth 2
```

The result should prefer:

- hierarchy
- counts
- truncation markers

over detailed node contents.

## `node summary`

Returns a graph-level summary for a root network.

This is the most important command for large networks.

Example:

```bash
houdini-cli node summary /obj/geo1
```

The response should include:

- root path
- total node count
- node type histogram
- terminal/output-like nodes
- likely entry nodes
- error/warning counts
- optional subnet count

Example:

```json
{
  "ok": true,
  "data": {
    "root": "/obj/geo1",
    "node_count": 128,
    "type_histogram": {
      "null": 18,
      "attribwrangle": 12,
      "blast": 9
    },
    "entry_nodes": [
      "/obj/geo1/file1"
    ],
    "terminal_nodes": [
      "/obj/geo1/OUT"
    ],
    "error_count": 1,
    "warning_count": 0
  }
}
```

## `node inspect`

Returns a focused summary for one node.

This is the bridge between traversal and full serialization.

It should include:

- structural summary
- connection summary
- interesting parm names
- error/warning info

But it should not default to full `asData()`.

## Default Limits

Traversal commands must have hard default limits.

Suggested defaults:

- `max_depth = 2`
- `max_nodes = 50`
- `include_parms = false`
- `include_connections = summary`
- `include_children = summary`

These defaults should apply even if the user forgets to bound the request.

## Truncation Rules

Every traversal result must clearly report truncation.

Example:

```json
{
  "ok": true,
  "data": {
    "count": 50,
    "truncated": true,
    "truncation": {
      "max_nodes": 50,
      "max_depth": 2
    },
    "next_hint": "Refine with --type, --name, --root, or increase --max-nodes"
  }
}
```

Truncation should not be silent.

## Summary Fields

## Required structural fields

Every node summary should include:

- `path`
- `name`
- `type`
- `category`

## Recommended counts

Where cheap to compute, also include:

- `child_count`
- `input_count`
- `output_count`

## Optional state flags

Only include when relevant or cheap:

- `display`
- `render`
- `bypass`
- `locked`

## Focused parm summary

Traversal should never dump all parm values by default.

Instead, summarize only:

- parm names with non-default values
- parm names with expressions
- parm names with keyframes
- parm names with references
- optionally top N changed parms

Suggested fields:

- `interesting_parms`
- `expression_parms`
- `keyframed_parms`
- `referenced_parms`

## Graph Summary Heuristics

For large networks, graph-level summaries are more useful than long flat node lists.

The traversal layer should support:

- node count
- type histogram
- nodes with cook errors
- nodes with warnings
- likely entry nodes
- likely terminal nodes
- branch points
- optionally simple chain compression

Example chain compression:

Instead of listing every node in a long linear sequence, summarize it as:

```json
{
  "chain": {
    "start": "/obj/geo1/file1",
    "end": "/obj/geo1/OUT",
    "length": 18
  }
}
```

This should be additive, not mandatory in V1.

## Implementation Strategy

## Internal traversal

Use ordinary HOM methods:

- `node.children()`
- `node.allSubChildren(...)`
- `node.allItems()`
- `node.allSubItems(...)`
- `node.glob(...)`
- `node.recursiveGlob(...)`
- `hou.node(path)`

Do not use `asData()` for broad discovery traversal.

## Filtering

Filtering should happen inside Houdini before returning results.

Do not:

- fetch a huge network
- filter client-side afterward

Do:

- traverse in Houdini
- apply type/name/category filters there
- stop once limits are reached

## Follow-Up Pattern

The intended workflow is:

1. `node summary` or `node find`
2. refine to a smaller set
3. `node inspect` on one or a few nodes
4. use `node get-parms-data`, `node get-inputs-data`, or `node get-data` only on the selected nodes

This preserves context and avoids accidental large dumps.

## Transport Efficiency

Traversal commands should return one compact payload per request.

That means:

- one remote traversal pass
- one summarized response
- no per-node chatty round trips from the client

This is where the design improves on the current MCP shape.

## Commands That Should Not Be Traversal Defaults

Do not make these default traversal outputs:

- full parameter dictionaries
- full node `asData()` payloads
- recursive child graphs with full metadata
- complete wiring payloads for every node
- network box / sticky note details unless requested

These should be opt-in expansions only.

## Tightened Traversal Surface

The first draft used five traversal commands. This can be tightened.

Recommended traversal V1:

- `node list`
- `node find`
- `node summary`
- `node inspect`

That is enough to support:

- broad discovery
- bounded search
- graph-level overview
- targeted follow-up

`node tree` can be deferred.

Reason:

- it overlaps heavily with `node list --max-depth N`
- the same data can be rendered with a client-side tree view if needed

If later added, it should be treated as presentation sugar over the same traversal backend, not a separate traversal primitive.

## Relationship To Data-Model Commands

Traversal and data-model commands should stay separate.

Traversal:

- query-oriented
- bounded
- summary-first

Data-model commands:

- state-oriented
- explicit
- targeted

This separation is what prevents accidental context blowup in large scenes.
