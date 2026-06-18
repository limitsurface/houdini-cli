# Houdini Recipes

Use this guidance when discovering, applying, creating, or managing Houdini
recipes.

## Recipe Categories

Houdini has four recipe categories:

- **Tool recipes** create one or more nodes and appear alongside node types in
  Tab menus. CLI node-type discovery marks them with `kind: recipe`, and
  `node create` can instantiate them by recipe key.
- **Decoration recipes** apply to an existing central node, create surrounding
  items, and may rewire connections.
- **Node presets** change parameters and optionally contents on an existing
  node.
- **Parameter presets** apply values to a parameter or multiparm.

Do not treat decorations or presets as ordinary creatable nodes. Tool and
decoration recipes may create multiple nodes or other network items, so inspect
the returned item map.

## CLI Workflow

Use `houdini-cli recipe list`, `find`, and `get` for discovery and inspection.
Use `recipe apply` and `recipe create` with the explicit recipe category.

Recipe creation writes Data HDA definitions and requires:

- an internal recipe key
- a user-facing label
- a library destination, expanded directory, or `Embedded`

Creation defaults to non-interactive behavior. Do not request drop-on-wire or
click placement through ad hoc Python. Those modes can block while waiting for
Network Editor input.

Treat `--force` creation as an in-place overwrite of the same internal recipe
key.

Do not delete individual recipe definitions through the CLI. Direct Data HDA
definition destruction can race Houdini's background recipe and help indexing.
Use Houdini's Recipe Manager, or uninstall an entire explicitly owned recipe
library outside the recipe command surface.

## Local Houdini References

- Recipe overview and categories:
  `../help_prepared/network/recipes.txt`
- Recipe scripting, application contexts, and pre/post scripts:
  `../help_prepared/network/recipe_scripting.txt`
- Recipe Builder:
  `../help_prepared/network/recipe_builder.txt`
- Declarative recipe data format:
  `../help_prepared/network/recipe_format.txt`
- HOM recipe save, apply, and inspection functions:
  `../help_prepared/hom/hou/data.txt`
