"""Structured help for the `session` command."""

SESSION_TOPIC = {'description': 'Inspect or control session-level state such as connectivity, frame, viewport screenshots, and '
                'viewport camera state.',
 'children': {'ping': {'description': 'Verify that Houdini is reachable over hrpyc/rpyc.',
                       'usage': 'houdini-cli session ping',
                       'examples': ['uv run houdini-cli session ping']},
              'save': {'description': 'Save the current Houdini scene to its existing HIP path.',
                       'usage': 'houdini-cli session save'},
              'save-as': {'description': 'Save the current Houdini scene to a new HIP path.',
                          'usage': 'houdini-cli session save-as <path> [--force]',
                          'notes': ['Houdini variables in the path are expanded',
                                    'existing destinations require --force',
                                    'missing parent directories are created']},
              'frame': {'description': 'Read or set the current timeline frame.',
                        'usage': 'houdini-cli session frame [<frame>]',
                        'examples': ['uv run houdini-cli session frame', 'uv run houdini-cli session frame 24']},
              'selection': {'description': 'Read the currently selected node paths from the Houdini UI.',
                            'usage': 'houdini-cli session selection [--include-hidden]',
                            'notes': ["the last path in `paths` is also returned as `current` and matches Houdini's "
                                      'global current node']},
              'screenshot': {'description': 'Capture a screenshot and report the Scene Viewer context it represents.',
                             'usage': 'houdini-cli session screenshot [--pane-name <name> | --index <n>] [--output '
                                      '<path>] [--frame <n>] [--width <px>] [--height <px>]',
                             'examples': ['uv run houdini-cli session screenshot --pane-name panetab1',
                                          'uv run houdini-cli session screenshot --index 0 --output '
                                          "'$HIP/houdini_cli/screenshots/view.png'"],
                             'notes': ['requires graphical Houdini UI',
                                       'viewer metadata is best-effort and never changes pane state',
                                       'when multiple Scene Viewers are active, use --pane-name or --index']},
              'viewport': {'description': 'Read or manipulate the active viewport in a Scene Viewer pane.',
                           'children': {'get': {'description': 'Read viewport type, free-camera state, and displayed network context.',
                                                'usage': 'houdini-cli session viewport get [--pane-name <name> | '
                                                         '--index <n>]'},
                                        'focus-selected': {'description': 'Frame the current Scene Viewer selection, '
                                                                          'like Space+F in the viewport.',
                                                           'usage': 'houdini-cli session viewport focus-selected '
                                                                    '[--pane-name <name> | --index <n>]',
                                                           'notes': ['requires graphical Houdini UI and an active '
                                                                     'Scene Viewer selection']},
                                        'axis': {'description': 'Switch the viewport to a fixed axis view or '
                                                                'perspective.',
                                                 'usage': 'houdini-cli session viewport axis <+x|-x|+y|-y|+z|-z|persp> '
                                                          '[--pane-name <name> | --index <n>]',
                                                 'notes': ['+x/-x map to right/left, +y/-y map to top/bottom, +z/-z '
                                                           'map to front/back']},
                                        'set': {'description': 'Set the perspective viewport camera translation, '
                                                               'rotation, and optional pivot.',
                                                'usage': 'houdini-cli session viewport set [--pane-name <name> | '
                                                         '--index <n>] [--t X Y Z] [--r RX RY RZ] [--pivot X Y Z]',
                                                'notes': ['only supports perspective views; switch with `session '
                                                          'viewport axis persp` if needed']}}}}}
