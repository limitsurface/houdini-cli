---
name: houdini-cli
description: Skill for working with the local Houdini CLI in this repo. Use when Codex needs to inspect or modify a live Houdini scene through the CLI and should defer command details to the CLI's built-in help instead of guessing or restating command syntax.
---

# Houdini CLI

## One-Time Setup

- If Houdini product docs are needed, first check for `skills/houdini-cli/help_prepared/`.
- If `skills/houdini-cli/help_prepared/` is missing, tell the user to copy their local Houdini help folder into `skills/houdini-cli/help/`.
- When prompting for that copy step, explain that the copied help folder should match a local install path like `..\\Houdini xx.x.xx\\houdini\\help` and that the next step will extract and filter a local searchable text corpus into `skills/houdini-cli/help_prepared/` without modifying the copied source.
- After the user confirms the raw help folder is in place, run `python skills/houdini-cli/scripts/prepare_houdini_help.py`.
- After the prepared tree exists, ask the user whether to delete `skills/houdini-cli/help/`.
- If the user approves deleting `skills/houdini-cli/help/`, delete it and then remove the one-time setup instructions from this skill so it only points at `help_prepared/`.

## General

- Prefer the CLI over ad hoc Python when the CLI already covers the task.
- When command shape or flags are unclear, call `uv run houdini-cli help` or `uv run houdini-cli help <command-path>`.
- Use the CLI help as the source of truth for command details.
- Use raw `rg` against `skills/houdini-cli/help_prepared/` for local Houdini doc lookup.
- Do not restate or duplicate command-specific help inside this skill.
