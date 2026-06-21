"""Structured help for the `parm` command."""

PARM_TOPIC = {'description': 'Read parameter values, structured parameter payloads, menu tokens, and apply parameter edits.',
 'notes': ['For OpenCL nodes after kernel edits, prefer: houdini-cli opencl sync <node-path>'],
 'children': {'get': {'description': 'Read the current value for one parameter.',
                      'usage': 'houdini-cli parm get <parm-path>',
                      'examples': ['uv run houdini-cli parm get /obj/cli_attrib_live/box1/sizex']},
              'full': {'description': 'Read the full structured parameter payload for one parameter.',
                       'usage': 'houdini-cli parm full <parm-path>',
                       'examples': ['uv run houdini-cli parm full /obj/cli_attrib_live/box1/t']},
              'menu': {'description': 'Inspect the menu items available on a parameter.',
                       'usage': 'houdini-cli parm menu <parm-path>',
                       'examples': ['uv run houdini-cli parm menu /obj/cli_attrib_live/box1/type']},
              'set': {'description': 'Apply one scalar or string parameter value from a CLI argument.',
                      'usage': 'houdini-cli parm set <parm-path> <value>',
                      'examples': ['uv run houdini-cli parm set /obj/cli_attrib_live/box1/sizex 2.5',
                                   'uv run houdini-cli parm set /obj/cli_attrib_live/copytopoints1/applymethod2 mult']},
              'tuple-set': {'description': 'Set all values on a tuple parameter in tuple order.',
                            'usage': 'houdini-cli parm tuple-set <parm-path> <value> <value> ...',
                            'examples': ['uv run houdini-cli parm tuple-set /obj/cli_attrib_live/xform1/t 1 2 3']},
              'text-set': {'description': 'Set a text parameter from stdin or a text file.',
                           'usage': "houdini-cli parm text-set <parm-path> --input <path-or-'-'>",
                           'examples': ['uv run houdini-cli parm text-set /obj/cli_attrib_live/wrangle1/snippet '
                                        '--input snippet.vfl',
                                        'Get-Content snippet.vfl | uv run houdini-cli parm text-set '
                                        '/obj/cli_attrib_live/wrangle1/snippet --input -']},
              'full-set': {'description': 'Apply a full structured parameter payload from stdin or a JSON file.',
                           'usage': "houdini-cli parm full-set <parm-path> --input <path-or-'-'>",
                           'examples': ['uv run houdini-cli parm full-set '
                                        '/obj/cli_attrib_live/copytopoints1/targetattribs --input payload.json']},
              'expression': {'description': 'Inspect, set, or clear parameter expressions.',
                             'children': {'get': {'description': 'Read a parameter expression and language.',
                                                  'usage': 'houdini-cli parm expression get <parm-path>'},
                                          'set': {'description': 'Set a parameter expression from an argument, file, '
                                                                 'or stdin.',
                                                  'usage': 'houdini-cli parm expression set <parm-path> [--language '
                                                           "hscript|python] (--text TEXT | --input <path-or-'-'>)"},
                                          'clear': {'description': 'Clear expressions/keyframes and optionally '
                                                                   'preserve the evaluated value.',
                                                    'usage': 'houdini-cli parm expression clear <parm-path> '
                                                             '[--keep-value]'}}},
              'reference': {'description': 'Create a typed HScript reference from one parameter to another.',
                            'usage': 'houdini-cli parm reference <target-parm> <source-parm> [--relative|--absolute]',
                            'notes': ['uses chs() for string parameters and ch() for numeric parameters',
                                      'relative references are the default']},
              'find': {'description': 'Search parameter names, raw values, expressions, and resolved references on one '
                                      'node.',
                       'usage': 'houdini-cli parm find <node-path> --query TEXT [--raw] [--expressions] '
                                '[--resolved-targets] [--max-matches N]',
                       'notes': ['query matching checks names, raw values, expressions, and resolved targets',
                                 'detail flags control which extra fields are returned in matching rows']},
              'refs': {'description': 'List resolved parameter references on one node or network.',
                       'usage': 'houdini-cli parm refs <node-path> [--external-to ROOT] [--recursive] [--max-refs N]',
                       'notes': ['--external-to marks references outside the supplied node or network root',
                                 '--recursive includes child nodes below node-path']},
              'template': {'description': 'Inspect or patch parameter-template UI and default metadata.',
                           'children': {'get': {'description': 'Read a focused parameter-template summary.',
                                                'usage': 'houdini-cli parm template get <parm-path> [--target '
                                                         'instance|definition]'},
                                        'set': {'description': 'Apply a partial parameter-template patch from JSON.',
                                                'usage': 'houdini-cli parm template set <parm-path> [--target '
                                                         "instance|definition] --input <path-or-'-'>",
                                                'notes': ['supports label, help, tags, default, numeric ranges, '
                                                          'strictness, join-with-next, and conversion to a named menu',
                                                          'definition targeting updates and saves the owning HDA '
                                                          'definition']}}},
              'default': {'description': 'Modify parameter-template defaults.',
                          'children': {'set': {'description': 'Set a template default from the current value or JSON.',
                                               'usage': 'houdini-cli parm default set <parm-path> [--target '
                                                        'instance|definition] (--current | --value JSON)'}}}}}
