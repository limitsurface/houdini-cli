"""Structured help for the `hda` command."""

HDA_TOPIC = {'description': 'Create, inspect, package, update, and validate Houdini digital assets.',
 'children': {'inspect': {'description': 'Summarize an HDA instance, definition, interface, sections, tools, and '
                                         'library.',
                          'usage': 'houdini-cli hda inspect <asset-node> [--parms] [--sections] [--tools]'},
              'definitions': {'description': 'List HDA definitions by library, category, namespace, or name.',
                              'usage': 'houdini-cli hda definitions [--library PATH] [--category CATEGORY] '
                                       '[--namespace NS] [--name TEXT] [--type-name TEXT] [--sections] [--max N|--all]',
                              'notes': ['broad scans are capped by default; use filters first in large sessions',
                                        '--sections includes embedded section names and sizes, which is intentionally '
                                        'omitted by default']},
              'libraries': {'description': 'List loaded HDA libraries and the definitions they provide.',
                            'usage': 'houdini-cli hda libraries [--library TEXT] [--definition TEXT] [--max N|--all]',
                            'notes': ['broad scans are capped by default; use filters first in large sessions']},
              'package': {'description': 'Create, publish, and validate an HDA from an existing plain subnet.',
                          'usage': 'houdini-cli hda package <subnet-path> --type-name TYPE --label LABEL --library '
                                   'PATH [options]',
                          'notes': ['the initial implementation packages existing subnets; explicit node lists and '
                                    'selection follow later']},
              'create': {'description': 'Convert an existing plain subnet into a digital asset.',
                         'usage': 'houdini-cli hda create <subnet-path> --type-name TYPE --label LABEL --library PATH '
                                  '[options]'},
              'update': {'description': 'Update selected HDA definition surfaces from an editable instance.',
                         'usage': 'houdini-cli hda update <asset-node> [--contents] [--interface] [--sections] '
                                  '[--tools] [--all] [--validate]',
                         'notes': ['without surface flags, contents is updated; --all uses contents -> interface -> '
                                   'sections -> tools -> save -> match -> validate']},
              'save': {'description': 'Save an HDA definition to its current or specified library.',
                       'usage': 'houdini-cli hda save <asset-node> [--library PATH]'},
              'instantiate': {'description': 'Create a new instance of an installed HDA type.',
                              'usage': 'houdini-cli hda instantiate <type-name> --parent PATH [--name NAME] [--input '
                                       'NODE] [--expanded]'},
              'match': {'description': 'Discard instance edits and match the current HDA definition.',
                        'usage': 'houdini-cli hda match <asset-node> [--force]'},
              'unlock': {'description': "Allow editing of an HDA instance's contents.",
                         'usage': 'houdini-cli hda unlock <asset-node> [--propagate]'},
              'install': {'description': 'Install an HDA library into the current Houdini session.',
                          'usage': 'houdini-cli hda install <library> [--force]'},
              'uninstall': {'description': 'Uninstall an HDA library from the current Houdini session.',
                            'usage': 'houdini-cli hda uninstall <library> --force'},
              'validate': {'description': 'Validate definition state, fresh instantiation, cooking, and interface '
                                          'behavior.',
                           'usage': 'houdini-cli hda validate <asset-node> [--fresh-instance] [--cook] [--frames CSV] '
                                    '[--strict] [--external-references]'},
              'parms': {'description': 'Inspect, apply, promote, and synchronize HDA parameters.',
                        'children': {'inspect': {'description': 'List published HDA parameters as compact flat rows '
                                                                'with folder paths.',
                                                 'usage': 'houdini-cli hda parms inspect <asset-node> [--folder PATH] '
                                                          '[--name TEXT] [--values] [--defaults] [--tree]'},
                                     'find': {'description': 'Search published HDA parameter names and labels.',
                                              'usage': 'houdini-cli hda parms find <asset-node> --name TEXT [--values] '
                                                       '[--defaults]'},
                                     'folders': {'description': 'List published HDA folders and child counts.',
                                                 'usage': 'houdini-cli hda parms folders <asset-node>'},
                                     'locate': {'description': 'Locate one published HDA parameter and report its '
                                                               'folder, value, and default.',
                                                'usage': 'houdini-cli hda parms locate <asset-node> <parm-name>'},
                                     'apply': {'description': 'Apply a declarative HDA parameter interface.',
                                               'usage': 'houdini-cli hda parms apply <asset-node> --input '
                                                        "<path-or-'-'> [--replace-all]",
                                               'notes': ['supports nested tabs, simple/collapsible folders, headings, '
                                                         'and separators',
                                                         'value parameters may define callback and callback_language '
                                                         '(python or hscript)',
                                                         'supports float_ramp and color_ramp parameters']},
                                     'promote': {'description': 'Promote an internal parameter onto the HDA interface.',
                                                 'usage': 'houdini-cli hda parms promote <asset-node> <internal-parm> '
                                                          '--name NAME [options]'},
                                     'defaults': {'description': 'Synchronize HDA defaults from current values.',
                                                  'usage': 'houdini-cli hda parms defaults <asset-node> '
                                                           '--from-current'}}},
              'section': {'description': 'List, read, write, or delete embedded HDA definition sections.',
                          'children': {'list': {'description': 'List embedded section names and sizes.',
                                                'usage': 'houdini-cli hda section list <asset-node>'},
                                       'get': {'description': 'Read an embedded section.',
                                               'usage': 'houdini-cli hda section get <asset-node> <name> [--output '
                                                        'PATH]'},
                                       'set': {'description': 'Create or replace an embedded section.',
                                               'usage': 'houdini-cli hda section set <asset-node> <name> --input '
                                                        "<path-or-'-'>"},
                                       'delete': {'description': 'Delete an embedded section.',
                                                  'usage': 'houdini-cli hda section delete <asset-node> <name> '
                                                           '--force'}}},
              'script': {'description': 'Manage common OnCreated, OnLoaded, OnUpdated, and PythonModule sections.',
                         'children': {'get': {'description': 'Read a common HDA script section.',
                                              'usage': 'houdini-cli hda script get <asset-node> <name>'},
                                      'set': {'description': 'Create or replace a common HDA script section.',
                                              'usage': 'houdini-cli hda script set <asset-node> <name> --input '
                                                       "<path-or-'-'>"},
                                      'delete': {'description': 'Delete a common HDA script section.',
                                                 'usage': 'houdini-cli hda script delete <asset-node> <name> '
                                                          '--force'}}},
              'tool': {'description': 'Inspect, create, or remove generated Tab-menu tool metadata.',
                       'children': {'inspect': {'description': 'Inspect Tools.shelf metadata.',
                                                'usage': 'houdini-cli hda tool inspect <asset-node>'},
                                    'set': {'description': 'Create or replace generated Tab-menu tool metadata.',
                                            'usage': 'houdini-cli hda tool set <asset-node> --submenu PATH [--context '
                                                     'CATEGORY] [--icon ICON]'},
                                    'remove': {'description': 'Remove generated Tab-menu tool metadata.',
                                               'usage': 'houdini-cli hda tool remove <asset-node> --force'}}}}}
