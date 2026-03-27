# Houdini CLI Python Runtime

## Decision

Use:

- `uv` for environment and dependency management
- Python `3.12` as the project target

## Why `uv`

`uv` is the right fit for this project because it gives:

- fast environment setup
- fast dependency installation
- simple project-local workflow
- clean separation from global Python state

This is preferable to relying on:

- global `pip`
- global `pytest`
- ad hoc local installs

## Why Python `3.12`

Recommended baseline:

- `>=3.12,<3.13`

Reasons:

- mature and broadly supported
- modern enough for comfortable development
- lower dependency risk than `3.13` or `3.14`
- less likely to hit packaging or library edge cases during early development

## Why not `3.14`

The current machine has Python `3.14.3`, but that is not the recommended project target.

Reason:

- newer Python versions are more likely to expose dependency lag
- this project does not benefit meaningfully from targeting the newest interpreter
- stability matters more than novelty here

## Why not `3.11`

Python `3.11` would also be viable, but `3.12` is the better balance:

- still conservative
- slightly more current
- no strong need to go further back

## Project Policy

The project should assume:

- development uses `uv`
- the project runtime is Python `3.12`
- the CLI itself runs in external CPython, not `hython`

The live Houdini session remains separate and is accessed through `hrpyc`/`rpyc`.

## Packaging Guidance

When the project is scaffolded:

- declare Python compatibility as `>=3.12,<3.13`
- keep runtime dependencies minimal
- keep dev dependencies project-local under `uv`

## Practical Outcome

This means:

- ignore the globally installed Python `3.14` for project targeting
- create and use a `uv`-managed Python `3.12` environment
- add dependencies inside that environment as implementation begins

## Recommendation

The runtime baseline for this project should be:

- `uv`
- Python `3.12`

That is the lowest-friction and lowest-risk setup for the Houdini CLI.
