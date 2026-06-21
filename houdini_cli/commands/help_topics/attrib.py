"""Structured help for the `attrib` command."""

ATTRIB_TOPIC = {'description': 'Inspect geometry attributes with summary-first reads.',
 'children': {'list': {'description': 'List attributes on a node, optionally filtered by class.',
                       'usage': 'houdini-cli attrib list <node-path> [--class point|prim|vertex|detail]'},
              'summary': {'description': 'List compact grouped attribute definitions.',
                          'usage': 'houdini-cli attrib summary <node-path> [--class point|prim|vertex|detail] '
                                   '[--max-attribs N]'},
              'geom-summary': {'description': 'Summarize cooked geometry element counts.',
                               'usage': 'houdini-cli attrib geom-summary <node-path> [--topology] [--max-prims N] '
                                        '[--max-histogram N]',
                               'notes': ['default output avoids primitive scans and returns only point, primitive, and '
                                         'vertex counts',
                                         '--topology adds primitive type and vertex-count histograms, capped by '
                                         '--max-prims']},
              'get': {'description': 'Read attribute metadata and sampled values.',
                      'usage': 'houdini-cli attrib get <node-path> <attrib-name> --class point|prim|vertex|detail '
                               '[--element N] [--limit N]'}}}
