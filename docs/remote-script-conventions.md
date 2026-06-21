# Remote Script Conventions

Internal Houdini-side Python is packaged under `houdini_cli/remote/` when it is large enough to have named operations, is shared by command modules, or benefits from isolated builder tests.

## Module Shape

Each remote domain module provides:

- One source string containing related Houdini-side functions.
- A `RemoteModule` declaration with a stable namespace.
- A fixed alias-to-function entrypoint map.
- Houdini function names beginning with `_houdini_cli_`.

Command modules call `RemoteModule.evaluate(connection, alias, *args)`. They do not construct remote function names or argument expressions with f-strings.

## Arguments And Results

- Arguments must be transport-safe primitives, lists, tuples, or dictionaries.
- `python_literal` is the only argument-to-source encoder for internal remote modules.
- Non-finite floats and arbitrary Python objects are rejected before execution.
- User-provided values must be arguments, not interpolated into the source block.
- Remote results should contain ordinary scalars and containers rather than HOM objects.
- Transport localization remains the command/domain caller's responsibility.

## Ownership

- Reusable or shared scripts belong in `houdini_cli/remote/<domain>.py`.
- Small command-specific scripts may remain command-adjacent until that command is refactored.
- Local fallback behavior remains beside the domain implementation; the remote package is not a second command layer.
- Remote scripts migrate with their owning module refactors. Do not perform repository-wide source movement without a behavioral reason.

## Exceptions

`houdini-cli eval` intentionally executes user-supplied source and is not an internal remote module. Recipe application may also execute recipe-owned source; it should retain its explicit data injection and validation boundary rather than pretending that dynamic recipe code is a fixed entrypoint.

## Verification

- Unit-test argument encoding, registered calls, unknown entrypoints, and invalid values.
- Keep focused tests around domain payload normalization.
- Smoke-test migrated entrypoints against live Houdini before committing.
- Compare repeated timings when the migrated path is performance-sensitive.
