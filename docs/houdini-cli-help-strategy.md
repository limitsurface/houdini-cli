# Houdini CLI Help Strategy

## Goal

The CLI is agent-facing, but it should still have strong built-in help.

Reason:

- a minimal skill can stay thin
- the agent can query the CLI directly for command usage
- command semantics stay documented close to the implementation
- this reduces duplication between skill text and CLI docs

## Principle

Keep runtime output machine-first.
Keep help text human-readable.

That means:

- normal command execution prints JSON only
- help commands print readable text
- help is the one place where human-oriented CLI UX is worth investing in

## Recommendation

Use `argparse`, but put real effort into:

- command descriptions
- subcommand descriptions
- argument help strings
- examples
- a dedicated `help` command

This gives you decent discoverability without switching the whole CLI to a more UX-heavy framework.

## Two Help Paths

## 1. Native parser help

Support standard forms:

- `houdini-cli --help`
- `houdini-cli parm --help`
- `houdini-cli node --help`
- `houdini-cli node get --help`

This should come from `argparse`.

## 2. Dedicated help command

Also support:

- `houdini-cli help`
- `houdini-cli help parm`
- `houdini-cli help node get`

This command should be designed for agents.

Why:

- agents can call a stable verb instead of depending on parser conventions
- you can shape the output more intentionally
- you can include examples and related commands

## Help Output Format

For the dedicated `help` command, I would support both:

- text output by default
- `--json` for agent parsing if needed

Example text output:

```text
COMMAND
  houdini-cli node get

PURPOSE
  Inspect one node.

MODES
  default          focused summary
  --section parms  parameter data
  --section inputs wiring data
  --section full   full node data

EXAMPLES
  houdini-cli node get /obj/geo1
  houdini-cli node get /obj/geo1/noise1 --section parms

RELATED
  houdini-cli node set
  houdini-cli node find
  houdini-cli node inspect
```

Example JSON output:

```json
{
  "ok": true,
  "data": {
    "command": "node get",
    "purpose": "Inspect one node.",
    "modes": [
      {
        "name": "default",
        "description": "focused summary"
      },
      {
        "name": "--section parms",
        "description": "parameter data"
      }
    ],
    "examples": [
      "houdini-cli node get /obj/geo1"
    ],
    "related": [
      "node set",
      "node find"
    ]
  }
}
```

## What Help Should Include

Every command help entry should include:

- command path
- one-line purpose
- important flags
- defaults
- truncation behavior if relevant
- 1-3 examples
- related commands

For traversal commands, help must also include:

- default `max_depth`
- default `max_nodes`
- truncation behavior
- how to refine a broad query

## What The Skill Should Do

The skill can stay extremely small.

It only needs to teach the agent:

- prefer the CLI over direct Python when possible
- call `houdini-cli help <command>` when uncertain
- use traversal commands before deep inspection
- use structured get/set commands before `eval`

The skill does not need to restate every command in detail.

## Why This Is Better

Without good CLI help:

- command knowledge drifts into prompts and skills
- the agent depends on stale external instructions
- every command change requires updating multiple places

With good CLI help:

- the CLI is the source of truth
- the skill stays minimal
- the agent can self-serve command details

## Implementation Notes

With `argparse`, I would:

- give each parser a strong `help` and `description`
- use `formatter_class=argparse.RawTextHelpFormatter` or similar where helpful
- attach examples in epilog text
- add a manual `help` subcommand that resolves command paths and prints curated help

The parser-generated `--help` remains useful, but the dedicated `help` subcommand becomes the agent's preferred entrypoint.

## Recommendation

Keep the stack as:

- `argparse`
- `rpyc`
- stdlib `json`

But explicitly invest in:

- curated command help
- a dedicated `help` subcommand
- optional JSON help output

That is the right compromise for an agent-facing CLI paired with a minimal skill.
