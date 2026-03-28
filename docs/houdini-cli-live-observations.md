# Houdini CLI Live Observations

## Purpose

This document records live behaviors discovered while validating the Houdini CLI against a real Houdini 21 session.

These points matter because they affect:

- CLI design
- CLI help text
- agent behavior
- the future minimal skill

They are not abstract design ideas. They are observed behaviors from the live system.

## Environment

Observed against:

- Houdini `21.0.512`
- `hrpyc` running inside Houdini
- external CLI using `rpyc`

## Observation 1: `rpyc` 6.x Does Not Work

Using `rpyc 6.x` against Houdini's `hrpyc` failed with:

- `invalid message type: 18`

Pinning the client to `rpyc 5.x` fixed the issue.

Current known-good client version:

- `rpyc 5.3.1`

### Implication

This is important enough to surface in:

- project runtime docs
- setup help
- troubleshooting help

The agent should not attempt to upgrade `rpyc` casually.

## Observation 2: `hou.Parm.valueAsData()` Is Tuple-Oriented

On a component parm like:

- `/obj/geo1/tx`

the call:

- `hou.Parm.valueAsData()`

returned tuple-shaped data such as:

```json
[5.25, 0.0, 0.0]
```

not just the scalar:

```json
5.25
```

### Implication

The CLI and the agent should not assume that a component parm always serializes to a scalar.

This should be mentioned in:

- `parm get` help
- `parm set` help
- the skill guidance for parameter reads and writes

## Observation 2b: Scalar Component Writes Need A Fast Path

Using:

- `hou.Parm.setValueFromData()`

on a component parm like:

- `ry`

with a scalar payload produced tuple-oriented behavior.

Observed example:

- intended: set rotation tuple to `(0, 30, 0)`
- actual with `setValueFromData(30.0)`: `(30, 0, 0)`

Using:

- `hou.Parm.set(30.0)`

produced the expected result.

### Implication

The CLI should not use `setValueFromData()` blindly for scalar payloads on component parms.

Current practical rule:

- scalar payloads use `parm.set(...)`
- structured payloads continue to use `parm.setValueFromData(...)`

This is important enough to preserve in help and future skill guidance because it is easy to assume the data-model write path is always the right default.

## Observation 3: `hou.OpNode.parmsAsData()` Can Return `None`

On a real GEO object node in Houdini 21:

- `parmsAsData(brief=False)`

returned:

- `None`

instead of a parameter dictionary.

### Implication

The CLI must treat this as valid behavior.

The agent should understand:

- absence of parm data is not necessarily a CLI bug
- node section reads may produce `null`

This should be called out in:

- `node get --section parms` help
- troubleshooting notes

## Observation 4: Broad Localization Of Houdini Object Collections Breaks

Trying to broadly materialize Houdini object collections over RPyC with `obtain()` caused failures such as:

- `cannot pickle 'SwigPyObject' object`

This happened when attempting to localize things like:

- `node.children()`
- other Houdini object collections

### Implication

Traversal must not rely on bulk localization of Houdini node objects.

Instead:

- keep traversal on live remote objects
- extract only primitive fields such as names, paths, counts, and flags
- avoid broad pickling/materialization of Houdini object collections

This is one of the key reasons the traversal design is summary-first.

## Observation 5: Structured JSON Input Is Safer Through Stdin

PowerShell quoting for inline JSON is fragile.

Structured commands such as:

- `node set --section inputs`

are more reliable when payloads are passed via:

- `--json -`
- stdin

instead of deeply escaped inline JSON strings.

### Implication

The agent should prefer stdin for non-trivial structured payloads.

This should be reflected in:

- command examples
- CLI help
- skill guidance

## Observation 6: Live Testing Early Was Necessary

Several important behaviors were not obvious from documentation or assumptions alone:

- the `rpyc` version mismatch
- tuple-oriented parm value serialization
- `parmsAsData()` returning `None`
- SWIG object pickling problems

### Implication

The implementation strategy with live checkpoints was correct and should continue.

This is especially important for:

- timeout tuning
- traversal defaults
- future error handling policy

## Guidance For The Future Skill

The eventual minimal skill should likely teach the agent:

- use the CLI for live scene interaction
- use local help files for Houdini docs
- prefer traversal before deep inspection
- prefer structured commands before `eval`
- prefer stdin for complex JSON payloads
- do not assume parameter data is always scalar or dict-shaped
- do not assume every node section returns data

## Guidance For CLI Help

The CLI help should explicitly mention at least:

- `rpyc 5.x` compatibility requirement
- stdin recommendation for complex JSON input
- `parm get` may return tuple-shaped data
- `node get --section parms` may return `null`

These are important enough to document close to the commands themselves.

## Recommendation

Keep this file as a running log of live-discovered behaviors that affect:

- command semantics
- transport reliability
- agent usage patterns

This will be more useful than trying to bury these details inside general design docs.
