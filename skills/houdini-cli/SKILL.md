---
name: houdini-cli
description: Skill for working with the local Houdini CLI in this repo. Use when you need to inspect or modify a live Houdini scene through the CLI and should defer command details to the CLI's built-in help instead of guessing or restating command syntax.
---

# Houdini CLI

## General

- Treat the directory containing this `SKILL.md` as the skill root. Resolve
  local references such as `help_prepared/`, `opencl/opencl_sops.md`, and
  `recipes/recipes.md` relative to that directory, regardless of whether the
  skill is installed under `.agents/skills`, `.codex/skills`, `.claude/skills`,
  or another harness-specific location.
- Discover available commands and subcommands with `houdini-cli help` before falling back to ad hoc approaches.
- Prefer the CLI over ad hoc Python when the CLI already covers the task.
- When command shape or flags are unclear, call `houdini-cli help` or `houdini-cli help <command-path>`.
- Use the CLI help as the source of truth for command details.
- Use fast text search against `help_prepared/` for local Houdini doc lookup, preferring `rg` when available. If help isn't prepared, remind user to consult installation instruction in repo README.
- After creating or rewiring a node network, set and verify the display/render/output flag on the intended result node. Do not leave display flags on heavy intermediate nodes unless the user specifically asked to inspect them. Stale display flags can make later CLI queries, viewport updates, and cooks appear much slower than the new work actually is.
- For the plain Solver SOP, and before unlocking simulation wrappers such as Vellum Solver, RBD Bullet Solver, Pyro Solver, or MPM Solver, inspect the HDA `DiveTarget` and `EditableNodes` sections. Resolve the declared dive target relative to the solver node and create custom nodes there; these networks are intended to remain editable while the asset stays locked. The plain Solver SOP should almost always be edited through its dive target, not unlocked. Do not guess the path or capitalization, and only unlock an asset when no suitable editable dive target exists and the task explicitly requires changing protected internals.
- COPs has been superseded by Copernicus. Legacy COP nodes are not compatible with the Copernicus context. Never use the legacy COP context unless the user explicitly requires it.
- Before any COP or Copernicus-related work, read `copernicus/copernicus.md`.
- Before OpenCL SOP geometry work, read `opencl/opencl_sops.md`.
- Before Gas OpenCL or DOP GPU microsolver work, read `opencl/opencl_dops.md`.
- For routine OpenCL work, use the documented patterns without broad native-node inspection. Inspect shipped kernels selectively when behavior is unfamiliar, solver-specific, synchronization-heavy, or unclear from the prepared help.

## Recipes

- Recipes store parameter presets or reusable node setups as Data assets. Tool recipes appear alongside ordinary node types in discovery with `kind: recipe`.
- Before creating, applying, or managing recipes, read `recipes/recipes.md`.

## VEX

- Treat the local Houdini VEX reference as the source of truth. Do not infer function names or signatures from C, C++, GLSL, or other syntactically similar languages.
- Before using a VEX function, verify that it exists in `help_prepared/vex/functions/<function>.txt`, resolved relative to this skill root.
- Do not use older or separate `references/functions/` trees as the source of truth when working with this Houdini CLI skill; they may be incomplete or generated from a different corpus.
- Check the documented `#context`, exact `:usage:` signatures, return type, overloads, and any geometry-handle or attribute-class constraints.
- Use `help_prepared/vex/contexts/` when context behavior or available globals are unclear.
- To discover functions by purpose, search descriptions and tags with `rg -i "<keyword>" help_prepared/vex/functions`.
- If the prepared help corpus is unavailable, do not guess VEX APIs. Remind the user to follow the local Houdini docs setup in the repo README.
