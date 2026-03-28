# Houdini CLI Implementation Checklist

## Goal

Build the CLI in small stages with live Houdini checkpoints between stages.

This is important because several key decisions should be validated against a real Houdini 21 session:

- traversal performance
- payload sizes
- timeout defaults
- behavior of `asData()` / `setFromData()`
- logging quality during development

The plan below is designed to avoid large implementation gaps before first contact with live Houdini.

## Modularity Constraint

Modularity is a hard requirement from the beginning.

Do not treat this as cleanup for later.
Do not allow a monolithic `main.py` or a generic "utils" dump to become the real architecture.

The implementation should be organized so that early working code already follows the intended module boundaries.

## Required Package Shape

The initial implementation should aim at a structure in this spirit:

```text
houdini_cli/
  __init__.py
  main.py
  transport/
    __init__.py
    rpyc.py
  commands/
    __init__.py
    session.py
    parm.py
    node.py
    query.py
    eval.py
  format/
    __init__.py
    envelopes.py
    errors.py
  runtime/
    __init__.py
    logging.py
    timeouts.py
  tests/
    ...
```

The exact names can change, but the architectural split should not.

## Boundary Rules

These rules should hold from the first commit of executable code.

### `main.py`

Should only:

- build the parser
- register command modules
- dispatch to handlers

It should not:

- contain business logic
- perform Houdini RPC directly
- format result payloads inline

### `transport/`

Should own:

- connection setup
- connection teardown
- retry policy
- access to remote `hou`
- low-level remote execution helpers

It should not know command semantics.

### `commands/`

Each command module should own one area:

- `session.py`
- `parm.py`
- `node.py`
- `query.py`
- `eval.py`

Each module should:

- register its parser/subcommands
- validate command arguments
- call transport/helpers
- return plain result dicts

Command modules should not depend on each other arbitrarily.

### `format/`

Should own:

- success envelope creation
- error envelope creation
- truncation metadata
- consistent JSON result shaping

This prevents every command module from inventing its own output contract.

### `runtime/`

Should own shared process behavior such as:

- logging setup
- debug mode
- timeout defaults

This keeps operational concerns out of command logic.

## Anti-Patterns To Avoid Early

Avoid these from the start:

- one large file with all commands
- parser setup mixed with business logic
- transport code copied across command modules
- ad hoc JSON envelope creation in each command
- a generic `helpers.py` that becomes a grab bag
- traversal logic mixed into node mutation code

These are exactly the patterns that force later refactors.

## Stage 0: Environment And Transport Spike

### Modularity requirements

Even the spike should honor module boundaries.

At minimum, stage 0 should already have:

- parser entry in `main.py`
- transport isolated in `transport/rpyc.py`
- session commands in `commands/session.py`
- `eval` command in `commands/eval.py`
- result envelope logic in `format/envelopes.py`

### Deliverables

- project skeleton
- `argparse` command entrypoint
- `rpyc` transport module
- JSON result envelope
- basic stderr logging
- `ping` command
- `eval` command

### Notes

At this stage, do not implement traversal or structured node/parm commands yet.
The only goal is to prove:

- CLI process launches
- connection works
- remote `hou` access works
- JSON/stderr separation is correct

### Unit tests

- result envelope formatting
- error envelope formatting
- basic transport connection mocking
- `eval` wrapper behavior with mocked remote execution

### Live test checkpoint

Run against a real Houdini session and verify:

- `ping` returns version and hip path
- `eval` can read trivial Houdini state
- stderr logging is useful but not noisy
- transport setup is stable

### Exit criteria

- live connection proven
- JSON contract stable enough to build on

## Stage 1: Parm Commands

### Modularity requirements

Parm logic should live in `commands/parm.py`.

If helper functions are needed, place parm-specific helpers alongside parm command code or in a clearly scoped module, not in a generic shared file.

### Deliverables

- `parm get`
- `parm set`
- default mode using:
  - `hou.Parm.valueAsData()`
  - `hou.Parm.setValueFromData()`
- `--full` mode using:
  - `hou.Parm.asData()`
  - `hou.Parm.setFromData()`

### Notes

This is the best early use of the new data model.
It is narrow, useful, and easy to validate live.

### Unit tests

- path resolution
- missing parm handling
- default versus `--full` mode dispatch
- JSON payload pass-through

### Live test checkpoint

Run against real parms and validate:

- scalar values
- vectors/tuples where applicable
- ramps
- multiparm-related values where easy to reproduce
- payload size differences between value mode and full mode

### Exit criteria

- parm reads and writes work on real nodes
- `--full` is meaningfully different from default mode
- no obvious schema surprises from Houdini 21

## Stage 2: Node Creation And Focused Inspection

### Modularity requirements

Node creation/deletion and focused node inspection should live in `commands/node.py`.

Do not place traversal-oriented inspection in the same helpers used for broad network query if their responsibilities start diverging.

### Deliverables

- `node create`
- `node delete`
- `node get`
- default `node get` returns focused summary only

### Notes

Do not jump to broad traversal yet.
First validate one-node inspection shape and create/delete flow.

### Unit tests

- create argument parsing
- delete handling
- focused summary envelope
- missing node errors

### Live test checkpoint

Validate:

- creating nodes in common contexts
- deleting created nodes
- focused summary usefulness on real SOP nodes
- whether the default focused summary is compact enough

### Exit criteria

- creation/deletion stable
- focused summary shape feels usable in practice

## Stage 3: Structured Node Sections

### Modularity requirements

Structured node section read/write stays under node command ownership, but shared formatting and transport remain separate.

If node-section handling starts to become large, split internal node command implementation by concern while keeping one public command module.

### Deliverables

- `node get --section parms`
- `node get --section inputs`
- `node get --section full`
- `node set --section parms`
- `node set --section inputs`
- `node set --section full`

### Notes

This stage introduces node-level data-model reads/writes, but still without broad traversal.

### Unit tests

- section dispatch
- payload routing to the correct HOM methods
- broad/full section error handling

### Live test checkpoint

Validate on real nodes:

- `parmsAsData()` payload size
- `inputsAsData()` wiring shape
- `asData()` size and practical usefulness
- whether `setParmsFromData()` and `setInputsFromData()` behave predictably
- whether `setFromData()` is too broad for common use

### Exit criteria

- section model is validated live
- you know whether any sections need narrowing or renaming

## Stage 4: Traversal V1

### Modularity requirements

Traversal must live in `commands/query.py` or an equivalent query-focused module.

Do not fold broad traversal into `commands/node.py`.

Reason:

- traversal and mutation have different defaults
- traversal has separate truncation and summary concerns
- keeping them separate prevents node inspection code from turning into a catch-all

If internal query helpers are needed, place them under a query-specific module tree.

### Deliverables

- `node list`
- `node find`
- `node summary`
- `node inspect`
- default truncation behavior
- explicit truncation metadata in responses

### Notes

This is the first stage where large-network behavior really matters.

Start with conservative defaults:

- `max_nodes = 50`
- `max_depth = 1`

Treat these as provisional until live testing confirms they are sensible.

### Unit tests

- traversal limit enforcement
- truncation metadata
- filtering behavior
- summary shape

### Live test checkpoint

Test against small, medium, and large networks and validate:

- payload sizes
- response usefulness
- whether `max_nodes=50` is too low/high
- whether `max_depth=1` is too shallow
- performance over `hrpyc`
- whether graph-level summaries are enough to avoid context blowup

### Exit criteria

- traversal defaults calibrated against reality
- summary fields feel sufficient
- no accidental giant payloads by default

## Stage 5: Attribute Inspection V1

### Modularity requirements

Attribute commands should live in their own command module, for example `commands/attrib.py`.

Do not bury attribute reads inside:

- `commands/node.py`
- `commands/query.py`
- generic eval helpers

This is a separate concern with its own payload limits and geometry-specific failure modes.

### Deliverables

- `attrib list`
- `attrib get`

### Notes

Keep this tool minimal.

It should be geometry-first and read-only:

- discover attribute definitions
- inspect one attribute
- support explicit element addressing

### Unit tests

- class validation
- missing geometry handling
- missing attribute handling
- `--element` behavior
- default limit/truncation behavior

### Live test checkpoint

Validate on real SOP geometry:

- common built-ins like `P`, `Cd`, `N`
- point, prim, and detail classes
- direct `--element` reads
- payload size with and without `--element`

### Exit criteria

- attribute inspection is usable without raw Python
- default payloads stay compact
- `--element` addressing feels practical

## Stage 6: Network Navigation V1

### Modularity requirements

Network navigation should stay separate from semantic query and mutation commands.

If implemented as a node command, keep the UI-driving logic isolated internally or in a dedicated module.

Do not let pane-control code leak into traversal or node data helpers.

### Deliverables

- `node nav`

### Notes

This command should be opinionated:

- accept one or more node paths
- require a shared parent network
- navigate the Network Editor
- select targets
- frame them

### Unit tests

- argument validation
- same-parent enforcement
- result envelope shape

### Live test checkpoint

Validate in a real Houdini UI session:

- single-node framing
- multi-node framing in one network
- behavior when nodes do not share a parent
- usefulness alongside `computer_use`

### Exit criteria

- the agent can reliably bring a network region into view
- the command reduces reliance on arbitrary pane-control Python

## Stage 7: Logging, Timeouts, And Error Hardening

### Modularity requirements

Do not push logging or timeout policy down into command modules ad hoc.

Centralize:

- logger setup
- debug behavior
- timeout defaults
- shared exception normalization

### Deliverables

- `--debug` logging mode
- production-quiet default logging
- timeout defaults for:
  - connect
  - eval
  - traversal
  - broad node reads
- stable error categorization

### Notes

This stage should happen after real command behavior is known.
Do not lock timeout values too early.

### Unit tests

- debug flag behavior
- timeout handling
- stderr/stdout separation under failure

### Live test checkpoint

Validate:

- timeout behavior under intentionally heavy queries
- whether logs are enough to diagnose failures
- whether JSON output remains clean under error conditions

### Exit criteria

- dev ergonomics are good
- runtime behavior is predictable

## Stage 8: Test Expansion And Cleanup

### Modularity requirements

Tests should mirror the module boundaries.

Suggested split:

- transport tests
- envelope/error tests
- command parser/handler tests by command area
- live integration tests by feature area

This helps enforce architecture indirectly.

### Deliverables

- broader unit coverage
- live integration suite
- command help improvements
- documentation cleanup

### Notes

This is where you stabilize, not where you discover the core design.

### Unit tests

- expand coverage around command variants
- traversal edge cases
- data-model edge cases

### Live integration tests

Cover at least:

- ping/eval
- parm get/set
- node create/delete
- node section reads/writes
- traversal commands on representative scenes

### Exit criteria

- enough confidence to use the CLI as the primary agent interface

## Stage 9: Node Type Discovery V1

### Modularity requirements

Node type discovery should live in its own command module, for example `commands/nodetype.py`.

Do not fold this into:

- `commands/node.py`
- `commands/query.py`
- generic `eval` helpers

This is distinct from scene traversal:

- traversal answers what nodes exist in the scene
- node type discovery answers what node types are available for creation

### Deliverables

- `nodetype list`
- `nodetype find`
- `nodetype get`

### Notes

This command family must be context-safe by default.

The live API probe showed that some categories, especially SOPs, can expose very large type registries once stock tools, HDAs, and packages are loaded.

So V1 should:

- require one category
- cap results by default
- return compact list/find items
- keep full metadata in `nodetype get`

### Unit tests

- category validation
- default limit/truncation behavior
- search filtering
- missing type handling
- compact versus full payload shaping

### Live test checkpoint

Validate against a real Houdini session:

- category counts on common categories like `sop`, `cop`, `lop`, `obj`
- namespaced and versioned HDA keys
- search usefulness for common queries like `wrangle`
- payload size remains safe under default settings

### Exit criteria

- the agent can discover creation tokens without dropping into raw `eval`
- default outputs stay compact enough for context safety
- full metadata is available only when explicitly requested

## Optional Later Stages

These should not block the first useful version:

- item capture/apply commands
- local help prep tooling
- minimal skill implementation
- optional `info help-root`

## Summary Of Live-Test Rhythm

The important discipline is:

1. build transport
2. live test
3. build parm commands
4. live test
5. build focused node commands
6. live test
7. build structured node sections
8. live test
9. build traversal
10. live test and recalibrate

This should keep the implementation grounded and prevent big speculative layers from accumulating before real validation.

## Modularity Acceptance Criteria

Before calling the first implementation pass "stable enough", the following should be true:

- no command logic lives primarily in `main.py`
- transport code is isolated
- traversal/query code is isolated from mutation code
- result envelope creation is centralized
- logging and timeout behavior are centralized
- tests are organized by module/feature boundary

If any of these fail, fix the architecture before adding more commands.
