"""Remote operations for parameter template mutation."""

from __future__ import annotations

from .module import RemoteModule


SOURCE = r"""
import hdefereval
import hou

def _houdini_cli_set_definition_default(parm_path, value):
    def apply():
        parm = hou.parm(parm_path)
        if parm is None:
            raise ValueError("Parameter not found: " + parm_path)
        node = parm.node()
        definition = node.type().definition()
        if definition is None:
            raise ValueError("Node type has no HDA definition: " + node.path())
        template_name = parm.tuple().name()
        group = definition.parmTemplateGroup()
        template = group.find(template_name)
        if template is None:
            raise ValueError("Parameter template not found: " + parm_path)
        updated = template.clone()
        components = updated.numComponents()
        if components > 1:
            values = value if isinstance(value, (list, tuple)) else [value] * components
            if len(values) != components:
                raise ValueError(
                    "Default arity mismatch: expected {}, got {}".format(
                        components, len(values)
                    )
                )
            updated.setDefaultValue(tuple(values))
        elif updated.type().name() in {"Menu", "Toggle", "Ramp", "Folder"}:
            updated.setDefaultValue(value)
        else:
            updated.setDefaultValue((value,))
        group.replace(template_name, updated)
        definition.setParmTemplateGroup(group)
        library = definition.libraryFilePath()
        definition.save(library)
        node.matchCurrentDefinition()
        return {
            "template_name": template_name,
            "default": updated.defaultValue(),
            "library": library,
        }
    return hdefereval.executeInMainThreadWithResult(apply)
"""

PARM_TEMPLATE_REMOTE = RemoteModule(
    namespace="parm_templates",
    source=SOURCE,
    entrypoints={"set_definition_default": "_houdini_cli_set_definition_default"},
)
