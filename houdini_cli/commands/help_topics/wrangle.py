"""Structured help for the `wrangle` command."""

WRANGLE_TOPIC = {'description': 'Create SOP, LOP, and DOP wrangles and synchronize spare parameters from VEX channel calls.',
 'notes': ["Spare parameter creation delegates to Houdini's native VEX expression helper.",
           'wrangle spare-parms sync preserves compatible existing spare parameters unless --clear is used.'],
 'children': {'create': {'description': 'Create a SOP Attribute, LOP Attribute, Geometry DOP, POP, or Gas Field wrangle.',
                         'usage': 'houdini-cli wrangle create <parent-path> [--kind KIND] [--name NAME] [--group GROUP] '
                                  '[--group-type TYPE] [--run-over CLASS] [--vex CODE_OR_- | --input PATH] '
                                  '[--create-spare-parms]'},
              'spare-parms': {'description': 'Synchronize or clear wrangle spare parameters.',
                              'children': {'sync': {'description': 'Create spare parameters from channel calls in the '
                                                                   'VEX snippet.',
                                                    'usage': 'houdini-cli wrangle spare-parms sync <node-path> '
                                                             '[--clear]'},
                                           'clear': {'description': 'Delete all spare parameters from a wrangle.',
                                                     'usage': 'houdini-cli wrangle spare-parms clear <node-path>'}}}}}
