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
- Treat `help_prepared/` as a prerequisite for Houdini scene work and use fast
  local text search against it, preferring `rg` when available. If the corpus is
  missing or unusable, pause Houdini CLI scene actions and remind the user to
  follow the help-preparation instructions in the repo README. Explain that the
  local corpus provides fast, comprehensive, version-matched searches without
  relying on partial web fetches. Continue without it only if the user
  explicitly asks to proceed after that warning.
- After creating or rewiring a node network, set and verify the display/render/output flag on the intended result node. Do not leave display flags on heavy intermediate nodes unless the user specifically asked to inspect them. Stale display flags can make later CLI queries, viewport updates, and cooks appear much slower than the new work actually is.
- For the plain Solver SOP, and before unlocking simulation wrappers such as Vellum Solver, RBD Bullet Solver, Pyro Solver, or MPM Solver, inspect the HDA `DiveTarget` and `EditableNodes` sections. Resolve the declared dive target relative to the solver node and create custom nodes there; these networks are intended to remain editable while the asset stays locked. The plain Solver SOP should almost always be edited through its dive target, not unlocked. Do not guess the path or capitalization, and only unlock an asset when no suitable editable dive target exists and the task explicitly requires changing protected internals.
- COPs has been superseded by Copernicus. Legacy COP nodes are not compatible with the Copernicus context. Never use the legacy COP context unless the user explicitly requires it.
- Before any COP or Copernicus-related work, read `copernicus/copernicus.md`.
- Before OpenCL SOP geometry work, read `opencl/opencl_sops.md`.
- Before Gas OpenCL or DOP GPU microsolver work, read `opencl/opencl_dops.md`.
- For routine OpenCL work, use the documented patterns without broad native-node inspection. Inspect shipped kernels selectively when behavior is unfamiliar, solver-specific, synchronization-heavy, or unclear from the prepared help.

## Scene Implementation Priorities

- Prefer existing native Houdini nodes when they express the operation clearly.
  For custom geometry, volume, and image processing that lives in a Houdini
  scene, prefer context-appropriate compiled languages over embedded Python.
- VEX should normally be the first custom-code option for geometry processing.
  Consider OpenCL when the workload is highly parallel, already GPU-resident,
  or large enough to benefit materially from GPU execution.
- Keep Copernicus processing on the GPU as much as practical. Prefer native COP
  nodes and OpenCL for per-pixel, per-voxel, neighborhood, iterative, and other
  bulk data processing. Avoid using Python to loop over image or geometry
  elements when the work can be expressed as an OpenCL kernel or suitable
  native node.
- Hybrid Python/OpenCL designs are appropriate when responsibilities are
  divided cleanly. Python can parse files, interpret irregular structures,
  prepare metadata, select resources, or convert external data into regular
  layers, attributes, or buffers; OpenCL should then perform the repeated
  high-volume processing.
- Do not default to Python SOPs, Python snippets, or embedded Python merely
  because they are easier to author. Use Python when it offers a genuinely
  clearer solution for orchestration, metadata, variable or string-heavy data
  wrangling, external libraries, or small workloads where its performance cost
  is insignificant.
- Before implementing geometry processing in a Detail Wrangle, consider
  whether the operation can run independently over points, primitives, or
  vertices, or whether an OpenCL or native-node formulation would provide
  useful parallelism.
- Detail Wrangles remain appropriate for inherently sequential work,
  topology-wide coordination, small global operations, prototypes, and cases
  where a parallel implementation would add disproportionate complexity.
- A simple Python or Detail Wrangle prototype is acceptable for proving
  behavior. If it becomes the delivered implementation, briefly assess its
  expected data scale and whether a practical parallel alternative exists.
- If a parallel approach fails or proves unreliable, prefer a correct fallback
  and record the performance tradeoff rather than forcing an unsuitable
  optimization.

## Recipes

- Recipes store parameter presets or reusable node setups as Data assets. Tool recipes appear alongside ordinary node types in discovery with `kind: recipe`.
- Before creating, applying, or managing recipes, read `recipes/recipes.md`.

## VEX

- Treat the local Houdini VEX reference as the source of truth. Do not infer function names or signatures from C, C++, GLSL, or other syntactically similar languages.
- Establish the VEX execution context and, for Wrangles, the run-over mode before writing code. Available globals, attribute shorthand, writable data, and opportunities for parallel execution depend on both.
- Before using a VEX function, verify that it exists in `help_prepared/vex/functions/<function>.txt`, resolved relative to this skill root.
- Do not use older or separate `references/functions/` trees as the source of truth when working with this Houdini CLI skill; they may be incomplete or generated from a different corpus.
- Check the documented `#context`, exact `:usage:` signatures, return type, overloads, and any geometry-handle or attribute-class constraints.
- When overload resolution is ambiguous, preserve explicit VEX types and consult the documented signatures before introducing casts.
- Use `help_prepared/vex/contexts/` when context behavior or available globals are unclear.
- To discover functions by purpose, search descriptions and tags with `rg -i "<keyword>" help_prepared/vex/functions`.
- If the prepared help corpus is unavailable, do not guess VEX APIs. Remind the user to follow the local Houdini docs setup in the repo README.
