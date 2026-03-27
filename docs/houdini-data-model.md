# Houdini Data Model Notes

## Scope

These notes summarize Houdini's newer JSON-like data model as documented in the local help bundle under:

- `houdini_help/hom.zip`
- `houdini_help/network.zip`

The relevant pages are:

- `hom.zip -> hou/data.txt`
- `hom.zip -> hou/Parm.txt`
- `hom.zip -> hou/OpNode.txt`
- `hom.zip -> hou/NetworkBox.txt`
- `hom.zip -> hou/NetworkDot.txt`
- `hom.zip -> hou/StickyNote.txt`
- `network.zip -> recipes.txt`
- `network.zip -> recipe_format.txt`
- `network.zip -> recipe_scripting.txt`

## What The New Model Is

The new model is a JSON-like serialization/apply layer used by Houdini recipes.

Recipes are declarative captures of:

- a parameter value or parameter state
- a node and some or all of its state
- a set of network items
- a tagged cluster of network items

The help pages describe this as the "recipe data format" or "data model". In practice, the important part for us is that HOM objects can now serialize themselves into plain Python dict/list/scalar structures and reconstruct themselves from those structures.

This is much better for a CLI than hand-assembling ad hoc dicts from `hou` calls.

## Main Object-Level APIs

### Parameters

On `hou.Parm`:

- `parm.valueAsData(evaluate=True, verbose=True)`
- `parm.setValueFromData(data)`
- `parm.asData(value=True, evaluate_value=False, locked=True, brief=True, multiparm_instances=True, metadata=False, verbose=False)`
- `parm.setFromData(data)`
- `parm.multiParmInstancesAsData(...)`
- `parm.setMultiParmInstancesFromData(data)`
- `parm.insertMultiParmInstancesFromData(data, index=0)`

What they are for:

- `valueAsData()` is the lightest-weight value capture.
- `setValueFromData()` is the inverse for value-only application.
- `asData()` captures a fuller parameter record, not just the raw value.
- `setFromData()` restores the fuller parameter record.
- the multiparm helpers matter because recipes treat multiparms as first-class serializable data, not a special case you must manually rebuild.

### Nodes

On `hou.OpNode`:

- `node.asData(nodes_only=False, children=False, editables=False, inputs=False, position=False, flags=False, parms=True, default_parmvalues=False, evaluate_parmvalues=False, parms_as_brief=True, parmtemplates="spare_only", metadata=False, verbose=False)`
- `node.setFromData(data, clear_content=False, force_item_creation=True, parms=True, parmtemplates=True, children=True, editables=True, skip_notes=False)`
- `node.parmsAsData(values=True, parms=True, default_values=False, evaluate_values=False, locked=True, brief=True, multiparm_instances=True, metadata=False, verbose=False)`
- `node.setParmsFromData(data)`
- `node.parmTemplatesAsData(name="", children=True, parmtemplate_order=False)`
- `node.appendParmTemplatesFromData(data, rename_conflicts=True)`
- `node.replaceParmTemplatesFromData(data)`
- `node.inputsAsData(ignore_network_dots=False, ignore_subnet_indirect_inputs=False, use_names=False)`
- `node.setInputsFromData(data)`
- `node.outputsAsData(ignore_network_dots=False, ignore_subnet_indirect_inputs=False, use_names=False)`
- `node.setOutputsFromData(data)`

What they are for:

- `asData()` / `setFromData()` are the main capture/apply pair for node state.
- `parmsAsData()` / `setParmsFromData()` let us update parameters without touching other node state.
- `parmTemplatesAsData()` and the corresponding "from data" methods are the route for spare parms and parameter interface edits.
- `inputsAsData()` / `setInputsFromData()` give structured wiring data, which is cleaner than manual `setInput` loops.

### Other Network Items

These also participate in the data model:

- `hou.NetworkBox.asData(...)` / `setFromData(data)`
- `hou.NetworkDot.asData(...)` / `setFromData(data)`
- `hou.StickyNote.asData(...)` / `setFromData(data)`

This matters because the model is broader than "just nodes". A network capture can include boxes, notes, and dots.

### High-Level `hou.data` Helpers

On `hou.data`:

- `hou.data.itemsAsData(items, ...)`
- `hou.data.selectedItemsAsData(...)`
- `hou.data.createItemsFromData(parent, data, ...)`
- `hou.data.clusterItemsAsData(items, target_node, ...)`
- `hou.data.createClusterItemsFromData(parent, data, target_node=None, ...)`

These are higher-level helpers over the per-object APIs.

They are useful when the unit of work is not "one node" or "one parm" but rather:

- a selected set of nodes/items
- a reusable snippet of a network
- a decoration/tool style cluster anchored around a target node

## Data Shapes

### Parm Value Data

`Parm.valueAsData()` returns a JSON-like scalar or structured value:

- int
- float
- string
- list
- dict

This is the most compact payload when you only need the value.

### Parm Data

`Parm.asData()` returns a fuller parameter record.

The help describes a brief mode where simple entries may collapse to just the value instead of a full dict. This is important for CLI stability:

- `brief=True` is compact and good for human inspection
- `brief=False` is safer if you want a consistent machine-facing schema

The docs also indicate parm data may include:

- value
- locked state
- multiparm instance data
- metadata

### Network Item Data

`recipe_format.txt` defines network item data for:

- nodes
- sticky notes
- network boxes
- network dots
- subnet indirect inputs

Important keys include:

- `type`
- `inputs`
- `outputs`
- `position`
- `color`
- `flags`
- `parms`

For wiring, Houdini prefers `inputs` on downstream items. Each input entry contains:

- `from`
- `from_index`
- `to_index`

### Cluster Data

Cluster data is a higher-level wrapper around network item data.

It contains:

- `tags`
- `children`

`tags` can include:

- `target_tag`
- `frame_tags`
- `selected_tags`
- `current_tag`

This is especially relevant for decoration/tool-like graph snippets where positions and references are relative to a target node.

### Recipe Data

Recipes are stored as data assets. The actual captured content lives in `data.recipe.json`.

The high-level structure includes:

- `data`
- `properties`
- `tool`
- `options`
- `info`

`info` includes a `data_version`, which suggests SideFX considers this a versioned declarative format rather than an incidental implementation detail.

## Practical Meaning For A CLI

The important shift is:

- old approach: call many narrow `hou` methods and manually shape output
- better approach: use Houdini's own serialization/apply methods and pass JSON through the CLI

For a CLI, this suggests a much smaller surface area:

- get parm value as data
- set parm value from data
- get parm state as data
- set parm state from data
- get node as data
- set node from data
- get wiring as data
- set wiring from data
- capture items/cluster as data
- recreate items/cluster from data

This would cover a large amount of current MCP functionality with fewer custom commands and less bespoke schema code.

## Recommended Defaults

For machine-facing commands:

- prefer `brief=False` when schema consistency matters
- prefer `metadata=False` unless you know you need it
- prefer value-only APIs when doing ordinary parm edits
- use node-level or item-level APIs only when you need structural edits

For interactive inspection:

- `brief=True` is useful for readable output
- `evaluate_value=True` or `evaluate_values=True` is useful for "current value" workflows

## Risks And Caveats

- The recipe format allows compact "brief" forms, which may be awkward if you want a stable schema.
- `setFromData()` is broader than `setValueFromData()`. Use the smallest inverse method that matches the intent.
- `parmtemplates="spare_only"` is a meaningful default. It avoids rewriting the full interface unless you explicitly want that.
- `children`, `editables`, and `clear_content` are powerful switches. A CLI should expose them carefully.
- Cluster and recipe flows are ideal for reusable graph snippets, but may be too high-level for simple single-node edits.

## Most Useful Methods For Us

If the goal is a lean Houdini CLI, the highest-value methods appear to be:

- `hou.Parm.valueAsData()`
- `hou.Parm.setValueFromData()`
- `hou.Parm.asData()`
- `hou.Parm.setFromData()`
- `hou.OpNode.parmsAsData()`
- `hou.OpNode.setParmsFromData()`
- `hou.OpNode.inputsAsData()`
- `hou.OpNode.setInputsFromData()`
- `hou.OpNode.asData()`
- `hou.OpNode.setFromData()`
- `hou.data.itemsAsData()`
- `hou.data.createItemsFromData()`
- `hou.data.clusterItemsAsData()`
- `hou.data.createClusterItemsFromData()`

If we trim aggressively, the first six are probably the best foundation.
