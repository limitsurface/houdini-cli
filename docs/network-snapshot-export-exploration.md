# Network Snapshot Export Exploration

Status: speculative; not approved for implementation

Date: 2026-07-13

## Summary

This document explores an optional command that exports selected Houdini network
state to a structured directory on disk. The intended benefit is to let agents
inspect a large, stable network using familiar source-navigation techniques:
file discovery, `rg`, partial reads, JSON tooling, and diffs.

The proposal is intentionally tentative. A snapshot could reduce repeated RPC
queries during prolonged investigation, but it could also encourage agents to
repeatedly serialize large networks when the existing summary-first CLI would
be faster, safer, and cheaper.

No implementation should begin until the usage policy, cost controls, and
reuse behavior in this document are agreed upon.

## Relationship to Live Traversal

The snapshot workflow must complement, not replace, the ordinary inspection
sequence described in `large-scene-traversal-improvements-spec.md`:

1. `node summary` establishes scale and broad shape.
2. `node find` narrows the area of interest.
3. `node neighbors --direction upstream|downstream` traces relevant topology.
4. Focused node and parameter reads answer local questions.
5. A snapshot is considered only when the investigation remains broad,
   repetitive, or comparative after those steps.

The normal CLI remains the default interface to live Houdini state. Snapshot
export is an escalation path for sustained forensic work.

## Why This May Be Useful

Agents are already effective at navigating large code and text corpora. A
carefully structured network snapshot could reuse those learned behaviors:

- enumerate files before opening them;
- search names, types, parameter names, expressions, paths, and code with `rg`;
- read only selected lines or node files;
- compare snapshots with ordinary diff tools;
- retain a stable view while the live Houdini session remains untouched;
- amortize one remote traversal across many investigative questions;
- share one captured state across later analysis passes.

The strongest use cases are:

- auditing expressions or file references across hundreds of nodes;
- locating repeated parameter patterns;
- inspecting many code-bearing nodes;
- comparing two deliberate scene states;
- preparing a refactor or migration plan;
- capturing reproducible evidence for a CLI or Houdini bug;
- investigating a large, mostly stable network over an extended period.

## Why This May Be Harmful

A snapshot is not inherently token-efficient. Exporting a large amount of JSON
only helps if the agent subsequently reads a small fraction of it. Poorly
designed or poorly routed usage could:

- serialize hundreds of megabytes to answer a small question;
- duplicate an unchanged snapshot repeatedly;
- create stale files that are mistaken for live state;
- bypass better bounded commands out of convenience;
- dump default parameter values that have little diagnostic value;
- expose machine-specific paths or other sensitive scene data unnecessarily;
- spend significant time traversing locked assets or nested shader networks;
- trigger unexpected cooks or evaluations;
- create noisy repository artifacts;
- turn one large remote response into one large local corpus without reducing
  the actual reasoning cost.

The feature should not ship unless it makes the good path easier than the
wasteful path.

## Core Hypothesis

For a broad investigation that requires many focused reads of the same stable
network, one bounded, reusable snapshot may cost less overall than repeated
live traversal and full-node queries.

This hypothesis should be measured rather than assumed.

## Non-Goals

The first experiment must not:

- replace `node summary`, `node find`, `node neighbors`, or focused reads;
- export cooked geometry;
- export a composed USD stage or USD prim attributes;
- embed textures, images, caches, or referenced files;
- recursively expand locked HDA internals by default;
- cook nodes merely to obtain evaluated values;
- infer semantic boundaries from node names or network layout;
- produce a single monolithic JSON document;
- write into the repository unless the caller explicitly chooses that path;
- run automatically as part of ordinary traversal;
- silently overwrite an existing snapshot;
- promise a lossless scene serialization or round-trip import format.

This is an inspection artifact, not a HIP replacement, backup mechanism, or
scene interchange format.

## Proposed Artifact Shape

A snapshot should be a directory, not one large file:

```text
snapshot/
├── manifest.json
├── nodes.jsonl
├── edges.jsonl
└── nodes/
    ├── <stable-node-id>.json
    ├── <stable-node-id>.json
    └── ...
```

### `manifest.json`

Contains snapshot identity, provenance, bounds, costs, and freshness data:

```json
{
  "schema": "houdini-cli.network-snapshot",
  "schema_version": 1,
  "created_at": "2026-07-13T09:30:00+01:00",
  "houdini_version": "21.0.729",
  "cli_version": "0.1.12",
  "hip_path": "D:/project/scene.hip",
  "hip_is_new": false,
  "hip_is_dirty": true,
  "frame": 1.0,
  "root": "/obj/patch",
  "scope": {
    "max_depth": 1,
    "max_nodes": 1000,
    "include_locked_assets": false,
    "cook": false,
    "parm_mode": "non-default",
    "value_mode": "authored"
  },
  "counts": {
    "nodes": 527,
    "edges": 603,
    "node_files": 527
  },
  "size": {
    "bytes": 18400231,
    "truncated_values": 3
  },
  "fingerprint": "sha256:...",
  "complete": true,
  "warnings": []
}
```

### `nodes.jsonl`

One compact searchable record per node:

```json
{"id":"n000123","path":"/obj/patch/merge9","type":"merge","category":"Sop","flags":"","inputs":11,"outputs":1,"detail":"nodes/n000123.json"}
```

JSON Lines is preferable here because agents can search or read bounded line
ranges without parsing the full index.

### `edges.jsonl`

One connection per line:

```json
{"src":"n000101","out":0,"dst":"n000123","in":6}
```

Paths should not be repeated on every edge when stable response-local IDs are
available from `nodes.jsonl`.

### Per-node files

Each file contains the detailed `asData()`-derived state for one node, normalized
into a documented JSON-safe schema. At minimum:

- path, name, type, category, and flags;
- structural input/output data;
- included parameter templates and values;
- expressions, keyframes, and references when requested;
- truncation markers for individual large values;
- the capture policy used for that node;
- errors encountered while serializing it.

The raw HOM structure should not be written blindly if it contains unstable,
opaque, or needlessly repeated data. A thin normalization layer is still
required even when the new `asData()` functions provide most of the source
payload.

## Tentative Command Surface

The command name is deliberately explicit:

```text
houdini-cli node snapshot export <root-path>
    --output <directory>
    [--max-depth N]
    [--max-nodes N]
    [--max-bytes N]
    [--max-value-bytes N]
    [--parm-mode none|non-default|all]
    [--value-mode authored|evaluated|both]
    [--include SECTION ...]
    [--include-locked-assets]
    [--cook]
    [--dry-run]
```

Potential companion commands:

```text
houdini-cli node snapshot inspect <snapshot-directory>
houdini-cli node snapshot freshness <snapshot-directory>
houdini-cli node snapshot diff <snapshot-a> <snapshot-b>
```

Only `export` and possibly `freshness` belong in the first experiment. Diffing
can initially use external tools.

## Default Capture Policy

If implemented, initial defaults should be conservative:

- no cooking;
- no locked-asset recursion;
- non-default parameters only;
- authored/raw values rather than evaluated values;
- structural connections and core flags included;
- expressions preserved where the selected `asData()` mode exposes them;
- hard node, total-byte, and per-value byte limits;
- output under an explicitly supplied directory;
- no overwrite;
- no stdout dump of snapshot contents.

The command's stdout response should contain only the artifact path and a small
manifest summary.

## Usage Guardrails

Preventing habitual or repeated dumping is part of the feature, not merely an
agent-prompt concern.

### 1. Required explicit output path

There should be no implicit current-directory dump. The caller must choose the
destination deliberately. Help should recommend an ignored temporary location
such as `.tmp/houdini-cli-snapshots/`.

### 2. Dry-run estimation

`--dry-run` should estimate:

- matching node count;
- likely file count;
- approximate serialized size;
- count of locked assets crossed or skipped;
- count of code-bearing or potentially large structured parameters;
- whether the requested scope exceeds recommended thresholds.

The estimate need not be byte-perfect. Its purpose is to expose order of
magnitude before committing to the export.

### 3. Cost threshold acknowledgement

Small bounded snapshots may proceed directly. A request above a documented
node or estimated-byte threshold should fail with an actionable message unless
the caller supplies an explicit acknowledgement such as:

```text
--allow-large-snapshot
```

This flag should not disable hard safety caps.

### 4. Reuse unchanged snapshots

Before exporting full node detail, calculate a cheap scope fingerprint from
available stable state such as:

- HIP path and modification state;
- root path;
- frame;
- capture options;
- node paths/types and relevant modification identifiers where HOM exposes
  them reliably.

If an existing snapshot at the destination has the same fingerprint, return it
as reusable rather than rewriting it. If a reliable cheap fingerprint cannot
be produced, do not pretend otherwise; report freshness as unknown.

### 5. No automatic overwrite

An existing non-matching snapshot should cause an error by default. Replacement
requires an explicit `--replace` option. The implementation should write to a
temporary sibling directory and rename atomically only after success.

### 6. Bounded recursion

Default depth should be shallow and finite. An unbounded recursive export must
require an explicit option and remain subject to node and byte caps.

### 7. Route guidance in help

Structured help should say when not to use the command. Suggested language:

> Use snapshots only for repeated, broad inspection of the same stable scope.
> For ordinary discovery, use `node summary`, `node find`, `node neighbors`, and
> focused parameter reads first.

### 8. Export reason

One speculative option is to require or encourage a short machine-readable
reason:

```text
--reason repeated-reference-audit
```

This would be recorded in the manifest and could help evaluate real usage. It
should not become bureaucratic if it provides no measurable benefit.

## Freshness and Staleness

Every snapshot is historical. Agents must be able to tell that immediately.

The manifest should include:

- capture timestamp;
- HIP path;
- whether the HIP was dirty;
- current frame and time;
- Houdini and CLI versions;
- root path and exact capture options;
- fingerprint or an explicit statement that freshness cannot be determined;
- whether the scene changed during capture, if detectable.

`snapshot freshness` could compare the manifest against the live session and
return:

```json
{
  "status": "fresh|stale|unknown",
  "reasons": ["frame_changed", "hip_dirty_state_changed"]
}
```

Agents should be instructed to check freshness before relying on an old
snapshot for claims about current live state.

## Parameter and Value Semantics

The export must distinguish authored state from evaluated state.

### `authored`

Capture literals, expressions, references, keyframes, and structured parameter
data without forcing evaluation or cooking. This should be the default.

### `evaluated`

Capture values evaluated at the recorded frame. This may execute expressions
or trigger dependency evaluation and therefore needs clear cost reporting.

### `both`

Capture authored and evaluated representations separately. Never replace an
expression with its evaluated value without recording the expression.

Large values need their own summaries and limits:

```json
{
  "kind": "string",
  "length": 284000,
  "included_bytes": 65536,
  "truncated": true,
  "sha256": "..."
}
```

The checksum allows equality checks without retaining the entire value.

## `asData()` Evaluation Questions

Before designing the final schema, implementation research should answer:

- Which current HOM node, parameter, input, and template `asData()` functions
  are available in the supported Houdini version?
- Which calls evaluate parameters or cook nodes?
- Which returned values are already JSON-safe?
- How are expressions, keyframes, references, ramps, and multiparms represented?
- Does node-level data duplicate parameter-template information excessively?
- What data changes between identical calls despite no scene edit?
- How do locked HDAs, editable nodes, compiled blocks, material networks, and
  LOP nodes differ?
- Can serialization be performed entirely inside Houdini and written directly
  to disk without returning the payload over RPyC?
- Which exceptions can occur midway through a node or network export?

The experiment should record representative payload sizes for several node
families before committing to a stable artifact schema.

## Security and Privacy Considerations

Full parameter data can contain:

- local and network file paths;
- usernames or machine names embedded in paths;
- resolver contexts;
- asset repository locations;
- Python, VEX, OpenCL, or shell code;
- credentials accidentally stored in parameters;
- production identifiers.

Accordingly:

- snapshots remain local by default;
- help warns against committing or sharing them without review;
- output paths should normally live under ignored temporary storage;
- no automatic upload, attachment, or Git staging occurs;
- future redaction support may be warranted, but naive path rewriting must not
  corrupt diagnostic value;
- manifests should make clear that the artifact may contain sensitive scene
  data.

## Failure and Partial Output

An interrupted export must never look complete.

- Write into a temporary directory.
- Set `complete: false` in the working manifest.
- Record per-node serialization failures without hiding them.
- On success, finalize counts and checksums, set `complete: true`, then rename
  atomically.
- On failure, either remove the temporary directory or leave it with an
  unmistakable `.incomplete` suffix when diagnostic retention is requested.
- A byte or node cap may produce a deliberately partial snapshot only if the
  manifest clearly records the exact truncation boundary.

## Experimental Success Metrics

The feature should be evaluated against real tasks, not merely whether it can
write JSON.

Measure:

- export duration;
- artifact size;
- node and value counts;
- number of subsequent live CLI calls avoided;
- number and size of snapshot files actually read by the agent;
- total tool-output tokens used with and without a snapshot;
- whether the snapshot became stale during investigation;
- frequency of duplicate export attempts;
- whether agents selected snapshot export before trying bounded live tools;
- correctness of conclusions compared with live Houdini state.

A useful experiment would repeat the production patch investigation in two
modes:

1. improved live traversal only;
2. improved live traversal followed by one bounded snapshot when justified.

The snapshot approach is successful only if it reduces total investigation
cost or materially improves accuracy on repeated deep questions.

## Prototype Scope

If approved for experimentation, the smallest useful prototype is:

1. `node snapshot export` with mandatory root and output directory.
2. `--dry-run` size/count estimation.
3. Directory artifact with manifest, node index, edge index, and per-node files.
4. One hierarchy depth setting and hard node/byte limits.
5. Structural data plus non-default authored parameter data.
6. No cooking, geometry, USD prim data, locked-HDA recursion, or overwrite.
7. Reuse detection for an unchanged destination where reliably possible.
8. Clear help routing users to live traversal first.

Do not implement diffing, evaluated values, all-default parameter export, or
arbitrary recursive asset expansion until the prototype has demonstrated value.

## Questions Requiring a Decision

- Should export require evidence that `node summary` or another discovery
  command was used first, or is documentation sufficient?
- What node and byte thresholds require `--allow-large-snapshot`?
- Should unchanged-scope reuse be destination-based or use a shared content
  cache?
- Can HOM provide a reliable cheap modification fingerprint for a network?
- Should per-node filenames use readable escaped paths, opaque stable IDs, or a
  hybrid?
- Is JSON Lines sufficient for indexes on very large scenes, or is a small
  SQLite index worth considering later?
- Should long code values remain embedded in node JSON or be split into
  extension-aware text files for better search and syntax tooling?
- Is `asData()` stable enough to expose with light normalization, or should the
  CLI define a narrower independent schema?
- How should snapshots behave when the live scene changes during export?
- Should snapshots be automatically eligible for cleanup after a retention
  period, or should lifecycle remain entirely manual?

## Recommendation

Do not add snapshot export to the immediate traversal implementation plan.

First implement directional traversal, network summaries, bounded parameter
projection, screenshot context metadata, and USD-stage summaries. Those changes
may remove enough friction that a full snapshot is rarely needed.

After those tools have been dogfooded, run a small `asData()` research spike to
measure payload shape, serialization cost, and fingerprint reliability. Build
the bounded prototype only if repeated live queries remain a meaningful source
of cost.

The desired outcome is not “agents can dump networks.” It is “agents can choose
one explicit, reusable snapshot when that is demonstrably cheaper than
continuing to query a large stable scope.”
