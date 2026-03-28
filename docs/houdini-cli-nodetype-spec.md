# Houdini CLI Node Type Discovery Spec

## Goal

Add a structured way to discover node types that are available for creation.

This is not scene traversal.
It is operator-type discovery against Houdini's loaded node type categories.

The main use cases are:

- find the creation token for a node type
- search available node types by name or description
- inspect one node type before using `node create`

## Scope

V1 should focus on category-scoped discovery for common Houdini node categories such as:

- `obj`
- `sop`
- `cop`
- `vop`
- `rop`
- `lop`
- `dop`

Support for less common or legacy categories can be added later if needed.

## Command Shape

Recommended command group:

```text
houdini-cli nodetype list --category sop
houdini-cli nodetype find --category sop --query wrangle
houdini-cli nodetype get --category sop attribwrangle
```

## Design Constraint: Context Safety

This command family must be conservative by default.

Real Houdini sessions can expose very large type registries:

- stock nodes
- SideFX tools
- HDAs
- versioned namespaced assets
- studio packages

So the CLI must avoid dumping giant operator catalogs into context by accident.

## Default Behavior

### `nodetype list`

List node types in one category with compact output only.

Required:

- `--category`

Default limits:

- `limit = 50`

Default sort:

- stable alphabetical sort by type key

Default fields:

- `key`
- `description`

Optional flags can widen the payload later, but the default should stay compact.

Example result:

```json
{
  "ok": true,
  "data": {
    "category": "sop",
    "count": 50,
    "items": [
      {
        "key": "attribwrangle",
        "description": "Attribute Wrangle"
      }
    ]
  },
  "meta": {
    "truncated": true,
    "limit": 50,
    "total_matches": 1984,
    "next_hint": "Refine with --query, --prefix, or increase --limit"
  }
}
```

### `nodetype find`

Search within one category.

Required:

- `--category`
- one filter such as `--query`

Recommended initial filters:

- `--query`
- `--prefix`

Matching should be case-insensitive.

`--query` should search at least:

- type key
- description

Default output and limits should match `nodetype list`.

### `nodetype get`

Return fuller metadata for one node type.

Required:

- `--category`
- `type_key`

Suggested result fields:

- `key`
- `name`
- `description`
- `category`
- `icon`
- `hidden`
- `deprecated`
- `namespace_order`
- `min_num_inputs`
- `max_num_inputs`
- `is_generator`

This is where fuller metadata belongs, not in `list` or `find`.

## Why Category Should Be Required

The same base name can exist across multiple categories.

Also, searching all categories by default increases:

- payload size
- ambiguity
- agent confusion

Requiring one category keeps the command predictable and context-safe.

## Type Key Versus Display Name

The raw Houdini node type key should be treated as the canonical identifier for creation.

Examples:

- `box`
- `attribwrangle`
- `kinefx::rigdoctor`
- `some_asset::tool::1.0`

This is important because the display label is not always enough to create the node.

## Live Metadata Confirmed Useful

The live API probe showed these fields are available and useful:

- `name()`
- `description()`
- `icon()`
- `hidden()`
- `deprecated()`
- `isGenerator()`
- `minNumInputs()`
- `maxNumInputs()`
- `namespaceOrder()`

These should form the basis of the V1 payload shape.

## Error Cases

Handle these clearly:

- invalid category
- unknown node type key
- empty query
- no matches

No-match results can either:

- return `ok: true` with `count: 0`
- or return a clear error

V1 should prefer:

- `ok: true`
- empty `items`

for search/list no-match cases.

## Modularity

This should live in a dedicated command module such as:

- `commands/nodetype.py`

Do not bury node type discovery inside:

- `commands/node.py`
- `commands/query.py`
- ad hoc `eval` wrappers

This is a separate concern:

- scene graph traversal is about existing nodes
- node type discovery is about available operator definitions

## Non-Goals

Not in V1:

- multi-category search by default
- deep inspection of parameter templates on node types
- tab-menu ranking emulation
- automatic recommendation logic
- documentation scraping for node types

## Recommendation

Keep V1 small and safe:

- `list`
- `find`
- `get`

with compact defaults and explicit truncation metadata.
