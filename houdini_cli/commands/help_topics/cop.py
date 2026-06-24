"""Structured help for the `cop` command."""

COP_TOPIC = {'description': 'Inspect cooked Copernicus image/layer data.',
 'children': {'info': {'description': 'Read cooked layer metadata for a COP node or selected output proxy node.',
                       'usage': 'houdini-cli cop info <node-path> [--output <index-or-name>]',
                       'notes': ['for output proxy nodes such as downstream nulls, the command infers the upstream '
                                 'producer output identity from the first input connection']},
              'sample': {'description': 'Sample one or more pixel locations from a COP output.',
                         'usage': 'houdini-cli cop sample <node-path> [--output <index-or-name>] (--x X --y Y | '
                                  "--points <json-or-'-'>)"},
              'export-image': {'description': 'Export a COP output to disk as raw data or a view-baked image.',
                               'usage': 'houdini-cli cop export-image <node-path> --mode raw|view '
                                        '[--aov <index-or-name>] [--output <path>] [--display <ocio-display>] '
                                        '[--view <ocio-view>]',
                               'notes': ['when --output is omitted, files are written under $JOB/tex/cli_images when '
                                         '$JOB is set, otherwise $HIP/tex/cli_images',
                                         'raw mode writes EXR with raw COP values and no display/view transform; use '
                                         'this for data inspection and round-trip tests',
                                         'view mode writes PNG by default and bakes the Houdini OCIO display/view for '
                                         'human inspection and image editing',
                                         'external OpenCV/NumPy arrays are commonly top-origin; when comparing raw EXR '
                                         'samples to Houdini COP pixel coordinates, map Y as needed']},
              'import-image': {'description': 'Create a File COP from an image on disk.',
                               'usage': 'houdini-cli cop import-image <image-path> --parent <copnet-path> '
                                        '[--name <node-name>] [--colorspace ocio|raw] [--set-display]',
                               'notes': ['uses $JOB or $HIP in the File COP filename parameter when the image is under '
                                         'one of those directories',
                                         'use --colorspace raw for data EXR round-trips and --colorspace ocio for '
                                         'ordinary display/image files',
                                         'reload and Add AOVs from File are pressed when those File COP buttons are '
                                         'available']}}}
