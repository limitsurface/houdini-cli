"""Structured help for the `opencl` command."""

OPENCL_TOPIC = {'description': 'Synchronize OpenCL node bindings and generated spare parameters across COP, SOP, and DOP contexts.',
 'notes': ['After editing an OpenCL kernel, run: houdini-cli opencl sync <node-path>',
           'Use opencl validate to check current port types, kernel/signature drift, and stale incompatible wires '
           'before or after syncing.',
           'Use --bindings-only when you want to refresh bindings/parms without changing the visible signature.'],
 'children': {'validate': {'description': 'Validate OpenCL COP signatures, SOP bindings, or DOP parameter rows against '
                                          'kernel #bind directives.',
                           'usage': 'houdini-cli opencl validate <node-path> [--details]',
                           'examples': ['uv run houdini-cli opencl validate /obj/geo1/work_here/opencl1']},
              'sync': {'description': 'Refresh an OpenCL node from #bind directives using COP signatures, SOP '
                                      'bindings, or Gas OpenCL DOP parameters.',
                       'usage': 'houdini-cli opencl sync <node-path> [--clear] [--bindings-only] '
                                '[--disconnect-invalid] [--no-preserve-spare-values] [--details]',
                       'examples': ['uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1',
                                    'uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1 --bindings-only',
                                    'uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1 --clear',
                                    'uv run houdini-cli opencl sync /obj/geo1/work_here/opencl1 '
                                    '--disconnect-invalid']}}}
