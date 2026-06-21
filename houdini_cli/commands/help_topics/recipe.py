"""Structured help for the `recipe` command."""

RECIPE_TOPIC = {'description': 'Discover, apply, and create Houdini recipes.',
 'notes': ['tool recipes create networks; decorations target existing nodes; node and parm presets target existing '
           'values',
           'interactive placement and drop-on-wire are intentionally excluded'],
 'children': {'list': {'description': 'List recipes, optionally by category.',
                       'usage': 'houdini-cli recipe list [--category tool|decoration|node-preset|parm-preset] '
                                '[--visible-only] [--limit N]'},
              'find': {'description': 'Search recipe keys and labels.',
                       'usage': 'houdini-cli recipe find --query TEXT [--category CATEGORY] [--visible-only] [--limit '
                                'N]'},
              'get': {'description': 'Inspect recipe metadata and stored payload.',
                      'usage': 'houdini-cli recipe get <recipe-key>'},
              'apply': {'description': 'Apply a category-specific recipe.',
                        'usage': 'houdini-cli recipe apply <tool|decoration|node-preset|parm-preset> <recipe-key> '
                                 '<target-option>'},
              'create': {'description': 'Create a category-specific recipe asset.',
                         'usage': 'houdini-cli recipe create <tool|decoration|node-preset|parm-preset> <recipe-key> '
                                  '[options]',
                         'notes': ['requires --label and --library; existing keys require --force']}}}
