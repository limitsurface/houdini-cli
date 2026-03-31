---
name: houdini-cli
description: Skill for working with the local Houdini CLI in this repo. Use when you need to inspect or modify a live Houdini scene through the CLI and should defer command details to the CLI's built-in help instead of guessing or restating command syntax.
---

# Houdini CLI

## General

- Discover available commands and subcommands with `houdini-cli help` before falling back to ad hoc approaches.
- Prefer the CLI over ad hoc Python when the CLI already covers the task.
- When command shape or flags are unclear, call `houdini-cli help` or `houdini-cli help <command-path>`.
- Use the CLI help as the source of truth for command details.
- Use raw `rg` against `skills/houdini-cli/help_prepared/` for local Houdini doc lookup. If help isn't prepared, remind user to consult installation instruction in repo README.
