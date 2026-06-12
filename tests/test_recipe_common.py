import json

from houdini_cli.commands import recipe_common


class FakeSection:
    def __init__(self, payload):
        self.payload = payload

    def contents(self):
        return json.dumps(self.payload)


class FakeDefinition:
    def __init__(self, payload):
        self.payload = payload

    def sections(self):
        return {"data.recipe.json": FakeSection(self.payload)}


class FakeNodeType:
    def __init__(self, label, payload):
        self.label = label
        self.payload = payload

    def description(self):
        return self.label

    def definition(self):
        return FakeDefinition(self.payload)

    def icon(self):
        return "DATA_recipe"


class FakeDataCategory:
    def __init__(self, node_types):
        self.node_types = node_types

    def nodeTypes(self):
        return self.node_types


class FakeHou:
    def __init__(self, node_types):
        self.node_types = node_types

    def dataNodeTypeCategory(self):
        return FakeDataCategory(self.node_types)


class FakeSession:
    def __init__(self, node_types):
        self.hou = FakeHou(node_types)


def _payload(category, *, visible=True, network_category="Cop"):
    return {
        "properties": {
            "recipe_category": category,
            "visible": visible,
            "nodetype_category": network_category,
        },
        "tool": {
            "network_categories": [network_category],
            "tab_submenus": ["Dynamics"],
            "icon": "COP_recipe",
        },
    }


def test_tool_recipe_items_filters_and_labels() -> None:
    session = FakeSession(
        {
            "tool": FakeNodeType("Flow Block", _payload("tool_recipe")),
            "decorator": FakeNodeType("Decorate", _payload("decoration_recipe")),
            "hidden": FakeNodeType("Hidden", _payload("tool_recipe", visible=False)),
            "sop": FakeNodeType("SOP Tool", _payload("tool_recipe", network_category="Sop")),
        }
    )

    assert recipe_common.tool_recipe_items(session, "Cop") == [
        {
            "key": "tool",
            "description": "Flow Block (recipe)",
            "label": "Flow Block",
            "kind": "recipe",
            "icon": "COP_recipe",
            "submenus": ["Dynamics"],
            "recipe_category": "tool_recipe",
        }
    ]
