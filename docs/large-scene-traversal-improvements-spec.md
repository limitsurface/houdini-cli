# Large-Scene Traversal Improvements Specification

Status: implemented

Date: 2026-07-13

Implemented: 2026-07-13

## Purpose

This specification proposes six improvements discovered while using the CLI to
inspect a production Houdini scene containing a SOP network with more than 500
top-level nodes and a downstream Solaris setup.

The current compact traversal formats worked well enough to recover the broad
architecture of both networks. The remaining problems were primarily avoidable
response duplication, unbounded detail inside otherwise focused responses, and
the absence of a USD-stage summary.

The goal of this work is to make broad production-scene inspection more
predictable and token-efficient without encoding assumptions about how artists
name or arrange their networks.

This document extends the principles in the archived
`houdini-cli-traversal-spec.md`. Existing command behavior should remain
compatible unless a caller explicitly requests one of the new modes.

## Design Principles

- Filter and aggregate inside Houdini before serializing a response.
- Keep existing compact row formats for graph-shaped results.
- Make every limit and truncation condition explicit.
- Prefer exact structural facts over semantic guesses.
- Preserve stable defaults for existing callers.
- Make expensive detail opt-in.
- Treat SOP, object, DOP, LOP, and other network layouts uniformly where HOM
  permits it.

## Explicit Non-Goals

This work must not:

- infer semantic boundaries from node names such as `OUT_*`, `MERGE_*`, or any
  other naming convention;
- assume that an asset is built inside one large object container;
- assume that components are split across multiple object containers;
- rank one Houdini network organization style as more canonical than another;
- collapse object merges, nulls, subnets, or other node types based on guessed
  artistic intent;
- inspect shader or asset internals as part of a default broad traversal;
- return full USD prim data, full parameter payloads, or full node serialization
  by default.

Semantic interpretation remains the responsibility of the caller. The CLI
should expose topology, types, flags, counts, and authored metadata accurately
enough for that interpretation to be made safely.

## 1. Directional Graph Traversal

### Problem

`node neighbors` currently traverses both inputs and outputs. This is useful for
local inspection, but inefficient when tracing a production network backward
from an output. Starting several traversals on adjacent upstream branches
repeats the same downstream nodes and edges in every response.

### Command Surface

Add a direction option:

```text
houdini-cli node neighbors <node-path>
    [--direction both|upstream|downstream]
    [--depth N]
    [--max-nodes N]
```

Rules:

- `both` remains the default for backward compatibility.
- `upstream` follows input connections from destination to source.
- `downstream` follows output connections from source to destination.
- The root node is always included.
- Depth zero returns only the root.
- Direction affects traversal only; returned edges retain their natural
  source-to-destination orientation.
- Existing node IDs, compact row fields, flags, and edge fields remain
  unchanged.

### Response Additions

Add the effective direction to the response:

```json
{
  "ok": true,
  "data": {
    "root": "/obj/asset/OUT",
    "direction": "upstream",
    "depth": 4,
    "nodes": {
      "cols": ["id", "p", "t", "f"],
      "rows": []
    },
    "edges": {
      "cols": ["src", "out", "dst", "in"],
      "rows": []
    },
    "meta": {
      "truncated": false,
      "max_nodes": 50
    }
  }
}
```

### Traversal Semantics

- Use breadth-first traversal so depth continues to describe graph distance
  consistently.
- Deduplicate nodes by stable Houdini path during one response.
- Deduplicate edges by source path, source output index, destination path, and
  destination input index.
- Preserve deterministic ordering. Within a breadth level, order upstream
  neighbors by destination input index and downstream neighbors by source
  output index followed by destination input index and path.
- Apply `max_nodes` before enqueueing further expansion.
- If the cap prevents visiting a discovered node, set `meta.truncated` to true.

### Acceptance Criteria

- Omitting `--direction` produces the current `both` behavior.
- An upstream traversal never includes a node reachable only through an output
  of the root or another visited node.
- A downstream traversal never includes a node reachable only through an input.
- Edge direction and port indices remain accurate in every mode.
- Cycles terminate safely without duplicate node rows.
- Tests cover branching, converging branches, cycles, disconnected nodes,
  subnet boundaries, and truncation.

## 2. Network Summary and Count-Only Modes

### Problem

Determining that a network is large currently requires returning a large node
list. In the production test, a 500-row bounded response was used only to learn
that the network contained at least 500 nodes and to get a rough sense of its
type distribution.

### Command Surface

Add a dedicated command:

```text
houdini-cli node summary <root-path>
    [--max-depth N]
    [--max-nodes N]
    [--top-types N]
    [--include-boundaries]
```

Also add a lightweight list mode:

```text
houdini-cli node list <root-path> ... --count-only
```

`node summary` is the preferred broad-discovery command. `node list
--count-only` exists for callers that already construct list filters and need
only the matching count.

### `node summary` Response

Suggested response:

```json
{
  "ok": true,
  "data": {
    "root": "/obj/asset",
    "scope": {
      "max_depth": 1,
      "max_nodes": 10000
    },
    "counts": {
      "nodes": 527,
      "subnets": 4,
      "bypassed": 8,
      "display": 1,
      "render": 1,
      "with_errors": 0,
      "with_warnings": 2
    },
    "type_histogram": [
      {"type": "attribwrangle", "count": 48},
      {"type": "xform", "count": 39},
      {"type": "object_merge", "count": 27}
    ],
    "category_histogram": [
      {"category": "Sop", "count": 527}
    ],
    "boundaries": {
      "entry_nodes": [],
      "terminal_nodes": [],
      "branch_nodes": []
    },
    "meta": {
      "truncated": false,
      "visited_nodes": 527,
      "top_types": 20
    }
  }
}
```

### Summary Semantics

- Count nodes and build histograms remotely in a single traversal pass.
- Do not serialize one row per visited node.
- `type_histogram` is ordered by descending count, then type name.
- `category_histogram` is ordered by descending count, then category name.
- `--top-types` limits returned histogram rows, not the types counted.
- When histogram rows are omitted, include an `other` count so totals remain
  reconcilable.
- Error and warning counts should read existing node state and must not cook by
  default.
- `max_depth` uses the same hierarchy semantics as `node list`, not graph-edge
  depth.
- `max_nodes` is a safety cap. If reached, counts describe only visited nodes
  and `meta.truncated` must be true.

### Structural Boundaries

`--include-boundaries` may report structural facts only:

- entry node: no connected inputs within the inspected scope;
- terminal node: no connected outputs within the inspected scope;
- branch node: more than one connected output within the inspected scope;
- fan-in node: more than one connected input within the inspected scope.

These classifications must not depend on node names or artist-specific node
types. Paths should be compact rows and independently capped, with explicit
per-list truncation metadata.

### `--count-only` Response

```json
{
  "ok": true,
  "data": {
    "root": "/obj/asset",
    "count": 527,
    "meta": {
      "truncated": false,
      "max_depth": 1,
      "max_nodes": 10000
    }
  }
}
```

All existing `node list` filters should apply before counting.

### Acceptance Criteria

- A summary of a 500-node flat network returns no per-node list unless
  `--include-boundaries` is requested.
- Histogram totals reconcile with the visited node count.
- Results are deterministic.
- Truncated summaries never imply that counts represent the complete scope.
- No node cooks solely because a summary was requested.
- `node list --count-only` honors name, type, category, depth, and node caps.

## 3. Bounded Parameter Discovery and Projection

### Problem

`node get --section parms` is intentionally a detailed operation, but some
parameters contain large structures such as ramps or multiparms. A focused node
inspection can therefore unexpectedly return thousands of tokens. Conversely,
using individual `parm get` calls requires the caller to know useful parameter
names in advance.

### Command Surface

Extend the existing parameter discovery commands rather than changing full
parameter serialization by surprise.

Proposed discovery surface:

```text
houdini-cli node parms list <node-path>
    [--non-default]
    [--name PATTERN]
    [--template-type TYPE]
    [--max-parms N]
    [--value-mode none|scalar|summary]
```

Proposed projection for structured node reads:

```text
houdini-cli node get <node-path> --section parms
    [--parm NAME ...]
    [--max-items N]
    [--structured-value full|summary]
```

If argparse limitations make repeated `--parm` awkward, a comma-separated
`--parms` option is acceptable, but repeated options are preferred because parm
names may contain unusual characters.

### Compatibility

- Existing `node get --section parms` without new flags retains its current
  full behavior.
- Broad traversal commands must continue to avoid full parameter payloads.
- `node parms list` keeps its existing compact row schema where possible.
- New limits apply only when explicitly supplied, unless a new command is
  introduced with documented safe defaults.

### Value Modes

`none`:

- return names, template types, and flags only;
- never evaluate or serialize values.

`scalar`:

- include values for scalar strings, integers, floats, toggles, and small fixed
  tuples;
- replace ramps, multiparms, large strings, and nested structured values with a
  summary.

`summary`:

- include bounded summaries for every value kind;
- examples: string length, tuple size, ramp point count, multiparm instance
  count, expression presence, and whether the value is default.

Suggested structured summary:

```json
{
  "p": "tonemapcurve",
  "t": "Ramp",
  "f": "n",
  "v": {
    "kind": "ramp",
    "point_count": 21,
    "basis": ["linear"],
    "has_expressions": true
  }
}
```

### Projection Rules

- `--parm` selects exact parameter or tuple names.
- A missing requested name is reported in `meta.missing`, not silently ignored.
- Preserve caller order for projected parameter names.
- `--max-items` limits nested collection items independently of the number of
  selected parameters.
- Truncated nested values include their total item count and a truncation flag.
- Large strings should expose length and an optional bounded preview rather than
  being split arbitrarily without metadata.
- Expressions should be represented explicitly and must not be mistaken for
  evaluated literals.

### Acceptance Criteria

- A Karma node with a 21-point ramp can be inspected without returning all ramp
  points.
- Callers can request exact parameters such as `engine`, `picture`, and
  `outputcs` in one response.
- Full existing parameter reads remain available.
- Every truncated value reports both truncation and total size where HOM makes
  the size available.
- Tests cover ramps, multiparms, folders, large strings, tuples, expressions,
  locked components, missing names, and default filtering.

## 4. Solaris/USD Stage Summary

### Problem

LOP node wiring describes how a stage is authored but not what the composed USD
stage contains. During the production test, cameras, lights, materials, render
settings, and bindings had to be inferred from LOP types and parameters. A
summary of the output stage would be more direct and authoritative.

### Command Surface

Introduce a Solaris-focused group:

```text
houdini-cli lop info <node-path>
    [--output INDEX]
    [--max-depth N]
    [--max-prims N]
    [--top-types N]
    [--include-paths]
```

The first version should be read-only and summary-first. The command accepts a
LOP node path and inspects the selected output's composed stage.

### Default Response

```json
{
  "ok": true,
  "data": {
    "node_path": "/stage/karmarendersettings",
    "output": 0,
    "stage": {
      "default_prim": "/geo",
      "up_axis": "Y",
      "meters_per_unit": 1.0,
      "time_codes_per_second": 24.0
    },
    "counts": {
      "prims": 184,
      "active": 182,
      "inactive": 2,
      "instances": 4,
      "prototypes": 2,
      "materials": 15,
      "lights": 7,
      "cameras": 2,
      "render_settings": 1,
      "render_products": 1,
      "collections": 2
    },
    "type_histogram": [
      {"type": "Mesh", "count": 40},
      {"type": "BasisCurves", "count": 26}
    ],
    "active_render_settings": "/Render/rendersettings",
    "active_camera": "/cameras/camera1",
    "composition": {
      "references": 0,
      "payloads": 0,
      "sublayers": 0
    },
    "meta": {
      "truncated": false,
      "max_prims": 10000,
      "included_paths": false
    }
  }
}
```

Fields unavailable or unauthored on a stage should be `null` or omitted
consistently; they must not be guessed from node names.

### Optional Path Lists

`--include-paths` adds bounded lists for:

- top-level prims;
- cameras;
- lights;
- materials;
- render settings and products;
- prototypes;
- prims with composition arcs.

Each list must have its own count, returned rows, and truncation state. The
default response returns counts only.

### Performance and Cooking

- Obtaining a LOP stage may require cooking the requested node. The response
  should state whether a cook occurred and how long stage acquisition and
  traversal took.
- Traverse prims once and accumulate counts/histograms in that pass.
- Do not serialize prim attributes, relationships, metadata dictionaries, or
  layer stacks by default.
- Respect `max_prims`. If capped, all affected counts must be clearly described
  as visited counts rather than complete-stage counts.
- Avoid expanding instance proxies by default. Report the chosen instance
  traversal policy in metadata.

### Errors and Diagnostics

Include existing node errors and stage acquisition failures in the normal error
envelope. Successful summaries may include compact diagnostic counts, but
should not return full Hydra or USD diagnostic logs unless explicitly requested
by a future diagnostic command.

### Acceptance Criteria

- The command rejects non-LOP nodes with a clear argument error.
- Multi-output LOP nodes honor `--output` and validate the index.
- A stage summary reports cameras, lights, materials, and render settings from
  composed USD prims rather than LOP node names.
- Default output remains compact for stages containing tens of thousands of
  prims.
- Instance traversal behavior is documented and tested.
- Truncated stage walks never present partial counts as complete counts.
- Tests cover empty stages, anonymous stages, inactive prims, instances,
  references, payloads, multiple cameras, multiple render settings, and invalid
  outputs.

## 5. Viewport Screenshot Context Metadata

### Problem

`session screenshot` reports the pane, path, frame, dimensions, and byte count,
but not what the pane was displaying. A second screenshot taken during Solaris
inspection captured the unchanged SOP view because the Scene Viewer had not
changed context. The image was valid, but its relevance could not be determined
from the command response alone.

### Command Surface

Keep the existing screenshot command unchanged:

```text
houdini-cli session screenshot [existing options]
```

Extend its successful response with a `viewer` object when metadata is
available:

```json
{
  "ok": true,
  "data": {
    "pane_name": "panetab1",
    "path": "D:/project/.tmp/view.png",
    "frame": 1,
    "width": 1280,
    "height": 720,
    "bytes": 1063256,
    "viewer": {
      "current_network": "/obj/patch",
      "pwd": "/obj/patch",
      "display_node": "/obj/patch/SOLARIS_patch_out",
      "category": "Sop",
      "viewport_renderer": "Houdini GL",
      "camera": null,
      "view_type": "perspective"
    }
  }
}
```

### Metadata Rules

- Metadata collection must not change the pane, current network, display node,
  camera, selection, viewport, or desktop layout.
- Use `null` for meaningful but absent values, such as no active camera.
- Omit fields that the Houdini version cannot expose reliably.
- The screenshot must still succeed if some metadata queries fail. Add compact
  warnings to `meta` rather than failing image capture.
- `current_network` and `display_node` must reflect actual UI/viewer state, not
  the node most recently queried through the CLI.
- For Solaris, report the displayed LOP/stage path when available.
- Preserve the existing top-level response fields for compatibility.

### Related Viewport Read

If the metadata implementation is reusable, expose the same shape through a
read-only command:

```text
houdini-cli session viewport get [--pane-name NAME | --index N]
```

This is optional for the first pass. Screenshot metadata is the required part.

### Acceptance Criteria

- A screenshot from a SOP viewer identifies the current SOP network and display
  node.
- A screenshot from a Solaris viewer identifies the current LOP context and
  displayed stage node where HOM exposes them.
- Camera and perspective views are distinguished.
- Metadata collection causes no visible UI state change.
- Failure to read one metadata field does not discard a successfully captured
  image.
- Existing screenshot callers continue to find all current response fields at
  their existing paths.

## 6. Shelf Tool Script Inspection

### Problem

The shelf command surface can find tools and replace their scripts, but cannot
read an existing script. This prevents inspection-before-edit workflows and
forces callers to use the unrestricted Python escape hatch for an otherwise
ordinary shelf operation.

### Command Surface

Add a read-only tool command:

```text
houdini-cli shelf tool get <tool-name>
```

The response includes the tool's internal name, label, owning shelves, complete
script text, and script character count. The exact script is returned by
default because safe editing requires a lossless read of the current source.

### Acceptance Criteria

- The command returns the complete script without evaluating or modifying it.
- Labels and all owning shelves are reported alongside the script.
- Missing tools use the standard argument-error envelope.
- Structured help and README shelf-edit workflows inspect before editing.
- Existing add, edit, delete, find, and list behavior remains compatible.

## Cross-Cutting Response Requirements

All six features should follow these rules:

- Continue using the standard success and error envelopes.
- Return compact column/row tables for repeated homogeneous records.
- Return named objects for small, heterogeneous summaries.
- Include effective limits in metadata.
- Include `truncated` at the level where truncation occurs.
- Distinguish a complete zero count from an unknown or truncated count.
- Keep paths absolute at command boundaries and compact them only where an
  existing response format defines a clear root.
- Do not silently cook except where stage acquisition inherently requires it;
  when cooking occurs, report it.
- Keep response ordering deterministic for stable tests and agent reasoning.

## Help and Documentation Requirements

Implementation must update:

- argparse help for every new option and command;
- structured help topics;
- root help workflows and legends where relevant;
- README examples for large-network traversal and Solaris inspection;
- tests that assert parser registration and structured help availability.

Help should steer broad production-scene inspection toward this sequence:

1. `node summary` for network scale and shape;
2. `node find` for targeted discovery;
3. `node neighbors --direction upstream` for graph tracing;
4. bounded parameter discovery or projection for selected nodes;
5. `lop info` for the composed Solaris result;
6. `session screenshot` with returned viewer context for visual confirmation.

## Suggested Implementation Order

1. Directional `node neighbors` traversal.
2. `node summary` and `node list --count-only`.
3. Bounded parameter discovery and projection.
4. Screenshot context metadata.
5. Solaris/USD stage summary.

The first two changes address the largest avoidable response volume with modest
implementation risk. Parameter projection removes the next major source of
unexpected payload growth. Screenshot metadata is comparatively isolated. USD
stage summarization is last because it introduces stage-cooking, instance, and
composition semantics that deserve dedicated live tests.

## Validation Plan

### Unit Tests

- Parser defaults and all new options.
- Directional traversal over synthetic branching and cyclic graphs.
- Deterministic summaries and histogram ordering.
- Truncation at node, boundary-list, parameter-item, and USD-prim levels.
- Parameter summaries for scalar, tuple, ramp, multiparm, expression, and large
  string values.
- Screenshot response assembly with complete, partial, and unavailable viewer
  metadata.
- USD accumulator behavior using small controlled stages or suitable fakes.

### Live Smoke Tests

Use disposable nodes and stages for mutation-free verification:

1. Compare `both`, `upstream`, and `downstream` traversal on a branched SOP
   graph.
2. Run `node summary` on a large flat network and verify it returns no node
   dump by default.
3. Inspect a Karma node containing a ramp using summary mode and exact parm
   projection.
4. Capture SOP and Solaris viewer screenshots and verify returned context.
5. Run `lop info` on empty, small composed, instanced, and multi-output stages.

### Production-Scene Regression

Repeat the traversal that motivated this spec:

- start at a selected final SOP null;
- establish network size without returning hundreds of node rows;
- trace only upstream branches;
- inspect selected render parameters without serializing the tonemap ramp;
- summarize the composed stage at the intended Karma endpoint;
- confirm from screenshot metadata whether the viewport is showing SOPs or
  Solaris.

The revised workflow should recover at least the same architectural overview
with materially fewer repeated node rows and no accidental large structured
parameter payloads.

## Definition of Done

This work is complete when:

- every new surface is implemented, documented, and covered by unit tests;
- existing command defaults and response fields remain compatible;
- full test and live smoke suites pass;
- production-scale traversals report explicit bounds and truncation;
- no feature relies on artist-specific node names or network organization;
- the motivating production-scene walkthrough can be repeated without either
  the 500-row node dump or repeated downstream neighbor graphs.
