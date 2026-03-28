# Houdini Skill Local Help Bootstrap Spec

## Goal

Keep the Houdini CLI skill lightweight in the repo while still allowing the agent to use a local Houdini help corpus on the user's machine.

The repo should contain:

- the skill
- the preparation instructions
- the preparation script

The repo should not contain:

- copied Houdini help content from a local SideFX install

## Reason

The local Houdini help folder is borrowed from a user machine / local install.

That means:

- it should not be bundled into the repo by default
- the skill should assume the help corpus may be missing on first use
- the setup flow should be local and repeatable

## Proposed Workflow

### 1. Skill ships without Houdini help content

The repo includes only:

- the `skills/houdini-cli/` skill
- a small setup script
- a small spec/reference note

### 2. Agent asks user to copy local Houdini help beside the skill

If the agent needs Houdini documentation and the local help corpus is not present, the skill should instruct the agent to ask the user to copy their local Houdini help folder next to the skill.

The skill should not:

- tell the agent to scrape the SideFX website
- tell the agent to download docs from the internet
- assume the docs are already present

Expected generic source path:

```text
..\Houdini xx.x.xx\houdini\help
```

Optional specific Windows default path example:

```text
C:\Program Files\Side Effects Software\Houdini 21.0.512\houdini\help
```

### 3. Agent runs a local preparation script

After the user copies the raw help folder in place, the agent runs a bundled script to process it into the shape we want.

That script should:

- validate the expected source folder exists
- build the prepared output tree
- avoid mutating the original copied source in place
- be safe to rerun

### 4. Agent uses the prepared local help tree

After preparation, the agent should search the processed help tree rather than guessing or relying on web docs.

This keeps responsibilities split cleanly:

- CLI help for CLI commands
- prepared local help tree for Houdini docs

## Repo-Side Layout

Current structure:

```text
skills/
  houdini-cli/
    SKILL.md
    agents/
      openai.yaml
    help/
      ...
    help_prepared/
      ...
    scripts/
      prepare_houdini_help.py
```

The important split is:

- `help/` is user-copied raw input
- `help_prepared/` is script-generated output

The raw `help/` tree should remain untouched after copy.

## Observed Source Layout

The copied Houdini help folder is not a clean text-only tree. It currently contains a mix of:

- top-level zip bundles such as `hom.zip`, `nodes.zip`, `network.zip`, `vex.zip`, `commands.zip`, `ref.zip`
- already-extracted topic folders such as `copernicus/`, `heightfields/`, `ml/`, `licenses/`, `examples/`, `videos/`
- top-level text/index/config files such as `index.txt`, `find.txt`, `_settings.ini`
- non-doc assets such as `.mp4`, `.hip`, `.hda`, `.otl`, images, and other binaries

This means the prep step should treat `help/` as a mixed-format source corpus, not assume everything is already extracted, and not assume everything is useful for agent lookup.

## Setup Behavior In The Skill

Later, the skill should say something close to:

- if Houdini docs are needed and prepared local help is missing, ask the user to copy their local Houdini help folder beside the skill
- then run the preparation script
- then search the prepared help tree

The skill should remain minimal and should not restate detailed Houdini docs behavior inside `SKILL.md`.

## Script Responsibilities

The preparation script should eventually handle:

- source folder validation
- selective extraction from zip bundles into a stable tree
- copying through already-extracted text trees only when they are relevant
- normalization into a search-friendly directory layout
- preserving useful SideFX path structure where possible
- repeatable reruns without corrupting the prepared output

## Preparation Strategy

The preferred approach is:

- leave `skills/houdini-cli/help/` unchanged as the raw source
- build a separate `skills/houdini-cli/help_prepared/` tree
- selectively extract only the high-value text archives first
- avoid indexing heavy media/examples by default

The initial high-value archives are:

- `hom.zip`
- `nodes.zip`
- `network.zip`
- `vex.zip`
- `commands.zip`
- `ref.zip`
- `help.zip`
- `crowds.zip`
- `destruction.zip`
- `dopparticles.zip`
- `expressions.zip`
- `feathers.zip`
- `fluid.zip`
- `muscles.zip`
- `ocean.zip`
- `pyro.zip`
- `solaris.zip`
- `vellum.zip`

These cover the main areas the agent is likely to need:

- HOM / Python API references
- node documentation
- network editor and parameter workflow docs
- VEX docs
- hscript / command docs
- general reference and help-system notes

Directories such as `videos/`, large image bundles, and example-heavy binary content should be excluded from V1 unless a concrete need appears.

## Proposed Prepared Layout

V1 should preserve source identity while making search cheap and predictable:

```text
skills/
  houdini-cli/
    help/
      ...
    help_prepared/
      hom/
      nodes/
      network/
      vex/
      commands/
      ref/
      help/
      crowds/
      destruction/
      dopparticles/
      expressions/
      feathers/
      fluid/
      muscles/
      ocean/
      pyro/
      solaris/
      vellum/
      copernicus/
      heightfields/
      ml/
      mpm/
      index.txt
      find.txt
      manifests/
        sources.json
        skipped.json
```

Notes:

- extracted archives and copied directories should sit together in one searchable tree
- `manifests/` records what was extracted, copied, or skipped so reruns are predictable

The exact included copied directories can still change after a more targeted pass, but they should stay conservative.

## Non-Goals For Now

Still not deciding yet:

- a full-text index format
- any embeddings/vector store
- HTML rendering or markup-to-Markdown conversion
- broad inclusion of example, video, or asset-heavy trees
- any more aggressive path flattening beyond top-level archive/topic grouping

## Next Step

Define the concrete transformation rules for `prepare_houdini_help.py`, including:

- source validation rules for `skills/houdini-cli/help/`
- which zip bundles are extracted in V1
- which existing directories are copied through in V1
- which file extensions and folders are explicitly skipped
- what manifest metadata is written for reruns

## Current V1 Script

Current script path:

```text
skills/houdini-cli/scripts/prepare_houdini_help.py
```

Current V1 behavior:

- extracts each selected zip into its own folder directly under `help_prepared/<zip-stem>/`
- copies selected text-heavy extracted directories directly under `help_prepared/`
- copies selected root help metadata files directly into `help_prepared/`
- writes manifests into `help_prepared/manifests/`
- leaves the raw `help/` folder in place
