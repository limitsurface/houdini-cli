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
- Use fast text search against `skills/houdini-cli/help_prepared/` for local Houdini doc lookup, preferring `rg` when available. If help isn't prepared, remind user to consult installation instruction in repo README.
- COPs has been superseded by Copernicus. Legacy COP nodes are not compatible with the Copernicus context. Never use the legacy COP context unless the user explicitly requires it.
- Before any COP or Copernicus-related work, read `skills/houdini-cli/copernicus/copernicus.md`.

## VEX

- Treat the local Houdini VEX reference as the source of truth. Do not infer function names or signatures from C, C++, GLSL, or other syntactically similar languages.
- Before using a VEX function, verify that it exists in `skills/houdini-cli/help_prepared/vex/functions/<function>.txt`.
- Check the documented `#context`, exact `:usage:` signatures, return type, overloads, and any geometry-handle or attribute-class constraints.
- Use `skills/houdini-cli/help_prepared/vex/contexts/` when context behavior or available globals are unclear.
- To discover functions by purpose, search descriptions and tags with `rg -i "<keyword>" skills/houdini-cli/help_prepared/vex/functions`.
- If the prepared help corpus is unavailable, do not guess VEX APIs. Remind the user to follow the local Houdini docs setup in the repo README.
