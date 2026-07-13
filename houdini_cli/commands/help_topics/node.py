"""Structured help for the `node` command."""

NODE_TOPIC = {'description': 'Inspect nodes, connections, errors, and apply structured node edits.',
 'notes': ['For OpenCL nodes after kernel edits, use: houdini-cli opencl sync <node-path>'],
 'children': {'create': {'description': 'Create a node or tool recipe under a parent network.',
                         'usage': 'houdini-cli node create <parent-path> <node-or-recipe-key> [--name <node-name>]',
                         'notes': ['tool recipes may create multiple nodes; --name applies only to ordinary nodes']},
              'rename': {'description': 'Rename one node and return its old and new paths.',
                         'usage': 'houdini-cli node rename <node-path> <new-name> [--unique]'},
              'copy': {'description': 'Copy one or more nodes to another parent while preserving internal wiring.',
                       'usage': 'houdini-cli node copy <node-path> [<node-path> ...] --parent <network-path>',
                       'notes': ['all source nodes must share one parent network',
                                 'returns an old-path to new-path map']},
              'move': {'description': 'Move one or more nodes to another parent while preserving internal wiring.',
                       'usage': 'houdini-cli node move <node-path> [<node-path> ...] --parent <network-path>',
                       'notes': ['all source nodes must share one parent network',
                                 'this reparents nodes; it does not change Network Editor positions']},
              'delete': {'description': 'Delete a node.', 'usage': 'houdini-cli node delete <node-path>'},
              'get': {'description': 'Read a focused node summary or a structured node section.',
                      'usage': 'houdini-cli node get <node-path> [--section parms|inputs|references|full] '
                               '[--external-only] [--parm NAME ...] [--max-items N] '
                               '[--structured-value full|summary]',
                      'examples': ['uv run houdini-cli node get /obj/cli_attrib_live/OUT --section inputs'],
                      'notes': ['repeat --parm with --section parms for exact, caller-ordered projection',
                                '--structured-value summary bounds ramps, strings, tuples, and other nested values',
                                'references reports parameter dependency targets and explicit input connections',
                                '--external-only applies to the references section and filters dependencies outside '
                                'the inspected root']},
              'errors': {'description': 'Read errors, warnings, and messages from one or more nodes.',
                         'usage': 'houdini-cli node errors <node-path> [<node-path> ...] [--cook]',
                         'notes': ['By default this reads existing messages without cooking the nodes.']},
              'connections': {'description': 'Read stable explicit input/output connection data for a node.',
                              'usage': 'houdini-cli node connections <node-path>'},
              'set': {'description': 'Apply structured node data to parms, inputs, or the full node payload.',
                      'usage': "houdini-cli node set <node-path> --section parms|inputs|full --json <payload-or-'-'>",
                      'notes': ['Use --section parms to batch multiple parameter edits on one node instead of '
                                'repeating parm set.',
                                'For --section inputs, pass a bare JSON array of connection rows, not an object '
                                'wrapper such as {"inputs": [...]}. Each row uses from/from_index/to_index fields.',
                                'Use named COP output/input ports when numeric indices are ambiguous.'],
                      'examples': ['uv run houdini-cli node set /obj/geo1/null1 --section inputs --json '
                                   '"[{\\"from\\":\\"/obj/geo1/box1\\",\\"from_index\\":0,\\"to_index\\":0}]"',
                                   'uv run houdini-cli node set /obj/copnet/opencl1 --section inputs --json '
                                   '"[{\\"from\\":\\"/obj/copnet/src\\",\\"from_index\\":\\"output1\\",\\"to_index\\":\\"input1\\"}]"',
                                   'Get-Content inputs.json | uv run houdini-cli node set /obj/copnet/opencl1 '
                                   '--section inputs --json -',
                                   'uv run houdini-cli node set /obj/copnet/merge1 --section inputs --json '
                                   '"[{\\"from\\":\\"/obj/copnet/A\\",\\"from_index\\":0,\\"to_index\\":0},{\\"from\\":\\"/obj/copnet/B\\",\\"from_index\\":0,\\"to_index\\":1}]"']},
              'flags': {'description': 'Read or set focused display, render, bypass, and Compress flags.',
                        'children': {'get': {'description': 'Read focused node flags.',
                                             'usage': 'houdini-cli node flags get <node-path>'},
                                     'set': {'description': 'Set one or more focused node flags.',
                                             'usage': 'houdini-cli node flags set <node-path> [--display BOOL] '
                                                      '[--render BOOL] [--bypass BOOL] [--compress BOOL]',
                                             'notes': ['Compress controls expanded or compact node presentation, '
                                                       'including COP live previews']}}},
              'list': {'description': 'List nodes under a root path in a compact row format with bounded traversal.',
                       'usage': 'houdini-cli node list <root-path> [--max-depth N] [--max-nodes N] [--count-only]',
                       'notes': ['Prefer node find first in large networks; list is best for shallow local traversal.',
                                 'See `help` root legends.node_rows for compact field meanings.']},
              'summary': {'description': 'Aggregate network counts and type/category histograms without returning one row per node.',
                          'usage': 'houdini-cli node summary <root-path> [--max-depth N] [--max-nodes N] '
                                   '[--top-types N] [--include-boundaries]',
                          'notes': ['Use this before broad node lists in large production networks.',
                                    'Boundary lists are structural, bounded, and opt-in.']},
              'find': {'description': 'Search for nodes by type, category, or partial name using the same compact row '
                                      'format as list.',
                       'usage': 'houdini-cli node find <root-path> [--type TYPE] [--category CATEGORY] [--name TEXT] '
                                '[--max-depth N] [--max-nodes N]',
                       'notes': ['Use this as the default discovery tool in large networks before node list.',
                                 'See `help` root legends.node_rows for compact field meanings.']},
              'parms': {'description': 'Discover parameters on one node.',
                        'children': {'list': {'description': 'List parameters on one node in a compact row format.',
                                              'usage': 'houdini-cli node parms list <node-path> [--non-default] '
                                                       '[--name TEXT] [--template-type TYPE] [--max-parms N] '
                                                       '[--value-mode none|scalar|summary]',
                                              'notes': ['See `help` root legends.node_parm_rows for compact field '
                                                        'meanings.']},
                                     'find': {'description': 'Search parameters on one node in the same compact row '
                                                             'format.',
                                              'usage': 'houdini-cli node parms find <node-path> [--name TEXT] [--type '
                                                       'TYPE] [--non-default] [--max-parms N] '
                                                       '[--value-mode none|scalar|summary]',
                                              'notes': ['See `help` root legends.node_parm_rows for compact field '
                                                        'meanings.']}}},
              'neighbors': {'description': 'Inspect local graph neighbors for one node with compact node and edge '
                                           'tables.',
                            'usage': 'houdini-cli node neighbors <node-path> '
                                     '[--direction both|upstream|downstream] [--depth N] [--max-nodes N]',
                            'notes': ['See `help` root legends.node_neighbors for compact field meanings.']},
              'nav': {'description': 'Navigate a Network Editor to one or more nodes.',
                      'usage': 'houdini-cli node nav <node-path> [<node-path> ...] [--no-frame] [--no-select] '
                               '[--no-current]',
                      'notes': ['requires shared parent network and graphical Houdini UI']}}}
