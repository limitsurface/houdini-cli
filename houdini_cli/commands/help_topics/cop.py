"""Structured help for the `cop` command."""

COP_TOPIC = {'description': 'Inspect cooked Copernicus image/layer data.',
 'children': {'info': {'description': 'Read cooked layer metadata for a COP node or selected output proxy node.',
                       'usage': 'houdini-cli cop info <node-path> [--output <index-or-name>]',
                       'notes': ['for output proxy nodes such as downstream nulls, the command infers the upstream '
                                 'producer output identity from the first input connection']},
              'sample': {'description': 'Sample one or more pixel locations from a COP output.',
                         'usage': 'houdini-cli cop sample <node-path> [--output <index-or-name>] (--x X --y Y | '
                                  "--points <json-or-'-'>)"}}}
