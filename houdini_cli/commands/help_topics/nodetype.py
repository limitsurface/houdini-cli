"""Structured help for the `nodetype` command."""

NODETYPE_TOPIC = {'description': 'Discover creatable node types and tool recipes by category, query, or prefix.',
 'notes': ['results use kind=node or kind=recipe; only tool recipes appear because decorations and presets apply to '
           'existing targets'],
 'children': {'list': {'description': 'List node types for a category.',
                       'usage': 'houdini-cli nodetype list --category obj|sop|cop|vop|rop|lop|dop|shop [--limit N]'},
              'find': {'description': 'Search node types by query text or prefix.',
                       'usage': 'houdini-cli nodetype find --category obj|sop|cop|vop|rop|lop|dop|shop (--query TEXT | '
                                '--prefix TEXT) [--limit N]'},
              'get': {'description': 'Read details for a specific node type key.',
                      'usage': 'houdini-cli nodetype get --category obj|sop|cop|vop|rop|lop|dop|shop <type-key>'}}}
