# Houdini CLI Agent-Only Stack

## Decision

This CLI is for agent use only.

That changes the stack recommendation materially:

- optimize for predictable machine I/O
- minimize dependencies
- avoid human-facing features
- keep command parsing and output boring

## Recommended Stack

- Python
- external CPython, not `hython`
- `argparse`
- `rpyc`
- stdlib `json`
- no `rich`
- no human mode
- no shell-oriented polish as a priority

## Why This Stack

For agent-only use, the important properties are:

- stable JSON output
- low dependency count
- low startup risk
- easy packaging
- easy debugging

The important properties are not:

- pretty help text
- colored output
- human-readable tables
- shell convenience features

That makes `argparse` a better default than `Typer`.

## Framework Choice

### `argparse`

Recommended default.

Why:

- stdlib
- simple
- stable
- sufficient for a compact command tree
- avoids framework overhead that does not benefit an agent

### Why not `Typer` by default

`Typer` is still viable, but for this use case it is mostly an implementation convenience, not an architectural advantage.

The agent does not benefit from:

- nicer help screens
- shell completion
- richer interactive UX

So the extra dependency is harder to justify.

## Runtime Model

Use an external Python environment for the CLI process.

Do not run the CLI under `hython` unless a hard dependency forces it.

Reason:

- the CLI should stay easy to install and update
- the CLI should not be tightly coupled to Houdini's embedded Python
- only the live Houdini session needs Houdini's Python environment

The transport layer bridges the two worlds.

## Transport

Use:

- `rpyc.classic.connect(...)`

This matches the current proven communication model with Houdini when `hrpyc` is running in the session.

## Output Contract

Stdout must contain JSON only.

No free-form status lines.
No banners.
No mixed human text and JSON.

Suggested success envelope:

```json
{
  "ok": true,
  "data": {}
}
```

Suggested error envelope:

```json
{
  "ok": false,
  "error": {
    "type": "hou.OperationFailed",
    "message": "..."
  }
}
```

Optional metadata:

```json
{
  "ok": true,
  "data": {},
  "meta": {
    "truncated": false
  }
}
```

## Stdout And Stderr Rules

### Stdout

- JSON only
- exactly one result object per invocation

### Stderr

Use for:

- logs
- diagnostics
- tracebacks
- debug output

This separation is important for agents and automation.

## Schema Guidance

Use plain dict/list/scalar payloads for Houdini-native data.

Do not over-model Houdini's data model in Python types.

Good candidates for light structure:

- result envelope
- error envelope
- traversal summaries
- truncation metadata

Bad candidates for heavy modeling:

- full `asData()` payloads
- arbitrary parameter value data
- cluster/item payloads

Those should remain mostly pass-through JSON.

## Validation

Start without `pydantic`.

Reason:

- the core Houdini data payloads are already dynamic
- adding strict models too early will create friction
- the main requirement is output consistency, not deep static typing

If validation becomes necessary later, add it only around:

- result envelopes
- traversal summary shapes
- command option normalization

## Human Features To Skip

Do not prioritize:

- human-readable mode
- pretty tables
- colors
- progress bars
- interactive prompts
- shell completion

These add complexity without helping the primary consumer.

## Logging Guidance

Logging should be:

- optional
- off or minimal by default
- directed to stderr

Recommended flags:

- `--quiet`
- `--debug`

But these should only affect stderr behavior, not stdout structure.

## Packaging

Use a normal `pyproject.toml` Python package.

Keep the dependency set small:

- required: `rpyc`
- optional: test dependencies only

Avoid unnecessary runtime packages in V1.

## Suggested Internal Layout

```text
houdini_cli/
  __init__.py
  main.py
  transport/
    rpyc.py
  commands/
    session.py
    parm.py
    node.py
    query.py
    eval.py
  util/
    errors.py
    jsonio.py
```

## Recommended Design Rules

- one command invocation produces one JSON object
- no command should emit human prose on stdout
- traversal must always report truncation explicitly
- broad traversal should return summaries, not full node payloads
- `eval` is the only generic escape hatch
- structured commands should stay narrower than `eval`

## Final Recommendation

For this project, the most suitable stack is:

- `argparse`
- `rpyc`
- stdlib `json`
- external CPython
- machine-only JSON contract

This is the lowest-friction, lowest-ambiguity stack for an agent-facing Houdini CLI.
