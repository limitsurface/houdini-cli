"""Per-command structured help topic data."""

from .ping import PING_TOPIC
from .wrangle import WRANGLE_TOPIC
from .session import SESSION_TOPIC
from .shelf import SHELF_TOPIC
from .eval import EVAL_TOPIC
from .parm import PARM_TOPIC
from .node import NODE_TOPIC
from .hda import HDA_TOPIC
from .cop import COP_TOPIC
from .opencl import OPENCL_TOPIC
from .attrib import ATTRIB_TOPIC
from .nodetype import NODETYPE_TOPIC
from .recipe import RECIPE_TOPIC

HELP_TREE = {
    "ping": PING_TOPIC,
    "wrangle": WRANGLE_TOPIC,
    "session": SESSION_TOPIC,
    "shelf": SHELF_TOPIC,
    "eval": EVAL_TOPIC,
    "parm": PARM_TOPIC,
    "node": NODE_TOPIC,
    "hda": HDA_TOPIC,
    "cop": COP_TOPIC,
    "opencl": OPENCL_TOPIC,
    "attrib": ATTRIB_TOPIC,
    "nodetype": NODETYPE_TOPIC,
    "recipe": RECIPE_TOPIC,
}
