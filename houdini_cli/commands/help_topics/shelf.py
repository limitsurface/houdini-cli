"""Structured help for the `shelf` command."""

SHELF_TOPIC = {'description': 'Inspect shelves, search shelf tools, and create or edit tool scripts.',
 'children': {'list': {'description': 'List known shelves in a compact row format.', 'usage': 'houdini-cli shelf list'},
              'tools': {'description': 'List tools on one shelf in a compact row format.',
                        'usage': 'houdini-cli shelf tools <shelf-name>'},
              'find': {'description': 'Search shelves and shelf tools by case-insensitive text.',
                       'usage': 'houdini-cli shelf find --query <text>'},
              'tool': {'description': 'Create, edit, or delete shelf tools.',
                       'children': {'add': {'description': 'Add a new Python shelf tool to one shelf from stdin or a '
                                                           'file.',
                                            'usage': 'houdini-cli shelf tool add <shelf-name> <tool-name> --label '
                                                     "<label> --input <path-or-'-'>"},
                                    'edit': {'description': 'Edit an existing shelf tool label or script and '
                                                            'optionally attach it to a shelf.',
                                             'usage': 'houdini-cli shelf tool edit <tool-name> [--label <label>] '
                                                      "[--shelf <shelf-name>] [--input <path-or-'-'>]"},
                                    'delete': {'description': 'Delete a tool from one shelf or all shelves and destroy '
                                                              'it if unused.',
                                               'usage': 'houdini-cli shelf tool delete <tool-name> [--shelf '
                                                        '<shelf-name>]'}}}}}
