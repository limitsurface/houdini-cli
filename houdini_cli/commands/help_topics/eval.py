"""Structured help for the `eval` command."""

EVAL_TOPIC = {'description': 'Execute Python against the live Houdini session when no structured command fits.',
 'usage': "houdini-cli eval (--code <python> | --input <path-or-'-'>)",
 'examples': ['uv run houdini-cli eval --code "print(hou.applicationVersionString())"',
              'Get-Content script.py -Raw | uv run houdini-cli eval --input -',
              'cat script.py | houdini-cli eval --input -'],
 'notes': ['--code and --input are mutually exclusive', '--input reads UTF-8 files or stdin when set to -']}
