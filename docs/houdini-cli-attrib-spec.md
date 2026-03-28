# Houdini CLI Attribute Tool Spec

## Goal

Add a minimal structured attribute interface for agent use.

This command surface should cover the common need:

- discover which attributes exist on a geometry-producing node
- inspect one attribute without dropping into arbitrary Python

It should stay summary-first and avoid large accidental payloads.

## Scope

This is a geometry attribute tool first.

V1 should target SOP-style geometry attributes:

- point
- prim
- vertex
- detail

Do not broaden this to every possible Houdini data domain yet.

## Commands

### `attrib list`

List attribute definitions available on a node's cooked geometry.

Example:

```text
houdini-cli attrib list /obj/geo1/OUT
```

Optional filters:

- `--class point|prim|vertex|detail`

Result should return compact definitions only, for example:

```json
{
  "ok": true,
  "data": {
    "node": "/obj/geo1/OUT",
    "classes": {
      "point": [
        {
          "name": "P",
          "size": 3,
          "data_type": "float"
        }
      ]
    }
  }
}
```

This command should not return raw attribute values.

### `attrib get`

Read a single attribute from cooked geometry on a node.

Example:

```text
houdini-cli attrib get /obj/geo1/OUT Cd --class point --element 12
```

Required arguments:

- `node_path`
- `attrib_name`
- `--class point|prim|vertex|detail`

Optional arguments:

- `--element N`
- `--limit N`
- `--stats min,max,mean,median`

`--element` is important and should be first-class.

It gives a direct way to ask for:

- point number
- prim number
- vertex number

For detail attributes, `--element` should be ignored or rejected cleanly.

## Default Behavior

`attrib get` should default to summary-safe behavior.

Even for a single attribute, values can explode in size on real geometry.

So `attrib get` must always enforce a cap unless the request is narrowed to one explicit element.

If `--element` is provided:

- return just that element's value

If `--element` is omitted:

- return a limited sample
- include metadata describing truncation

`--limit` should apply to the number of returned elements, not bytes or tuples.

Example:

```json
{
  "ok": true,
  "data": {
    "node": "/obj/geo1/OUT",
    "attribute": {
      "name": "Cd",
      "class": "point",
      "size": 3,
      "data_type": "float"
    },
    "values": [
      {
        "element": 0,
        "value": [1.0, 0.0, 0.0]
      }
    ]
  },
  "meta": {
    "truncated": true,
    "limit": 10
  }
}
```

## Suggested Defaults

- `limit = 10`

This should be treated as a safe starting point, not a permanent contract.

## Attribute Statistics

It is worth supporting a small set of common aggregate operations for numeric attributes.

This is useful because the agent often needs to understand an attribute distribution without pulling many raw values.

Suggested flag:

```text
houdini-cli attrib get /obj/geo1/OUT pscale --class point --stats min,max,mean,median
```

Suggested support:

- `min`
- `max`
- `mean`
- `median`

This should only apply to numeric attributes:

- ints
- floats

For non-numeric attributes, reject stats cleanly or return a clear unsupported error.

For vector-valued numeric attributes, the implementation should choose one of two behaviors and document it clearly:

- compute per-component stats
- require a future explicit component selector

V1 should prefer per-component stats if it is simple and unambiguous.

Example:

```json
{
  "ok": true,
  "data": {
    "node": "/obj/geo1/OUT",
    "attribute": {
      "name": "pscale",
      "class": "point",
      "size": 1,
      "data_type": "float"
    },
    "stats": {
      "min": 0.02,
      "max": 1.4,
      "mean": 0.31,
      "median": 0.28
    }
  }
}
```

The important rule is:

- use stats when the agent wants distribution information
- use raw values only for a sample or a specific element

## Implementation Notes

V1 can be based on cooked geometry from the target node:

- resolve node
- get `node.geometry()`
- fetch the requested attribute definition
- read only the requested class and values

Use Houdini HOM directly for this.

Do not attempt to push this through the new `asData()` model unless there is a clear benefit.

## Error Cases

Handle these clearly:

- node not found
- node has no geometry
- attribute not found
- invalid class
- element out of range
- unsupported stats request for non-numeric attributes

## Design Rules

- summary-first by default
- single-attribute reads only
- explicit class required for `attrib get`
- support direct element addressing
- no giant arrays by default
- capped reads even for one attribute
- lightweight numeric stats preferred over large raw samples when possible

## Non-Goals

Not in V1:

- bulk attribute dumps
- attribute writing
- spreadsheet-like pagination
- multi-attribute queries in one command
- non-geometry domains unless a real need emerges
