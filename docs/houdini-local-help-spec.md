# Houdini Local Help Spec

## Goal

Use a prepared local Houdini help corpus for documentation lookup instead of:

- scraping the SideFX website
- building a heavy docs subsystem into the CLI

The CLI should focus on live Houdini interaction.
The local help corpus should handle documentation discovery.

## Core Decision

Do not make Houdini documentation lookup a major CLI feature.

Instead:

- prepare the local help files once
- extract zipped docs into a searchable directory tree
- let the agent use normal filesystem search/read tools to discover and open docs

This is simpler, faster, and more reliable.

## Responsibilities

### CLI

The CLI is responsible for:

- talking to a live Houdini session
- traversal/query of the scene
- structured get/set operations
- controlled escape hatch via `eval`

The CLI is not responsible for:

- browsing the Houdini documentation corpus
- scraping online docs
- maintaining a second query language for help files

### Local help corpus

The local help directory is responsible for:

- serving as the source of truth for Houdini docs
- being searchable with normal agent file tools
- preserving enough original structure to follow SideFX help conventions

### Skill

The skill is responsible for telling the agent:

- where the local help root is
- when to search local help instead of guessing
- that CLI help is for CLI commands, not Houdini docs

The skill should stay minimal.

## Directory Strategy

The help corpus should be prepared into an extracted directory.

Suggested structure:

```text
houdini_help/
  archives/
    hom.zip
    network.zip
    ...
  extracted/
    hom/
      hou/
        Parm.txt
        OpNode.txt
        data.txt
        ...
    network/
      recipes.txt
      recipe_format.txt
      recipe_scripting.txt
    nodes/
      ...
```

If keeping the original zips in place is useful, that is fine, but the extracted tree should be the default search target.

## Why Extraction Is Recommended

Extracting the help files once is worth it because it gives:

- faster repeated access
- straightforward recursive search
- simpler agent discovery
- no zip-reading logic needed during normal operation
- predictable file paths for references

This matters more than storage efficiency.

## Search Model

The agent should use ordinary file discovery tools against the extracted help root.

Examples:

- search for `asData`
- search for `setFromData`
- search for `recipe_format`
- open `hom/hou/Parm.txt`
- open `network/recipe_format.txt`

This is preferable to inventing a separate CLI docs API.

## Optional Preparation Steps

The prepared help corpus should ideally:

- extract all relevant zip archives
- preserve internal paths
- retain text-friendly files
- avoid requiring runtime decompression for common lookups

Optional nice-to-haves:

- a small index file describing major subtrees
- a note explaining SideFX path conventions

For example:

- `hom/hou/...` for HOM Python docs
- `network/...` for recipe/data-model docs
- `nodes/...` for node docs

## Minimal CLI Involvement

The CLI does not need a full `houdini-help` command.

If anything is added, it should be minimal and informational only.

Example:

- `houdini-cli info help-root`

Possible output:

```json
{
  "ok": true,
  "data": {
    "help_root": "D:/vibe_code/houdini_CLI/houdini_help/extracted"
  }
}
```

Even this is optional if the skill already knows the help path.

## What Not To Do

Avoid:

- website scraping
- HTML parsing at runtime if extracted text is already available
- duplicating help search features inside the CLI
- maintaining a separate command taxonomy for documentation lookup

These add complexity without solving the real problem.

## Recommended Workflow

For a command question:

- use `houdini-cli help ...`

For a Houdini API or node documentation question:

- search the local extracted help corpus

For a live scene question:

- use the CLI

This split keeps responsibilities clear.

## Recommendation

The best design is:

- extracted local help corpus
- agent uses filesystem tools for discovery
- CLI stays focused on live Houdini control
- minimal skill teaches the split between CLI help and Houdini help

That is the simplest and most maintainable arrangement.
