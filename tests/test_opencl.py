from argparse import Namespace

from houdini_cli.commands import opencl


class FakeParm:
    def __init__(self, value):
        self.value = value
        self.last_set = None

    def evalAsString(self):
        return self.value

    def set(self, value):
        self.last_set = value


class FakeOpenclNode:
    def __init__(self) -> None:
        self.set_parms_calls = []
        self.kernel_parm = FakeParm("#bind layer src? val=0\n#bind layer !&dst\n#bind parm gain float val=2\n")
        self.runover_parm = FakeParm("layer")
        self._group = FakeParmTemplateGroup()
        self.signature_data = {"inputs": [{"input#_name": "src", "input#_optional": True}], "outputs": [{"output#_name": "dst"}]}

    def path(self):
        return "/obj/cops/opencl1"

    def setParms(self, payload):
        self.set_parms_calls.append(payload)

    def parm(self, name):
        if name == "kernelcode":
            return self.kernel_parm
        if name == "options_runover":
            return self.runover_parm
        if name == "inputs":
            return FakeParm(0)
        if name == "outputs":
            return FakeParm(0)
        if name == "bindings":
            return FakeParm(0)
        return None

    def parmTemplateGroup(self):
        return self._group.copy()

    def setParmTemplateGroup(self, group):
        self._group = group.copy()

    def parmsAsData(self, brief=False):
        return self.signature_data


class FakeTemplate:
    def __init__(self, name, label="", template_type="Float") -> None:
        self._name = name
        self._label = label
        self._template_type = template_type

    def name(self):
        return self._name

    def label(self):
        return self._label

    def type(self):
        return FakeType(self._template_type)


class FakeFolderParmTemplate(FakeTemplate):
    def __init__(self, name, label) -> None:
        super().__init__(name, label, "Folder")
        self._children = []

    def addParmTemplate(self, template):
        self._children.append(template)

    def parmTemplates(self):
        return tuple(self._children)


class FakeType:
    def __init__(self, name) -> None:
        self._name = name

    def name(self):
        return self._name


class FakeParmTemplateGroup:
    def __init__(self, entries=None) -> None:
        self._entries = list(entries or [])

    def entries(self):
        return tuple(self._entries)

    def append(self, entry):
        self._entries.append(entry)

    def insertBefore(self, name, entry):
        for index, current in enumerate(self._entries):
            if current.name() == name:
                self._entries.insert(index, entry)
                return
        self._entries.append(entry)

    def remove(self, name):
        self._entries = [entry for entry in self._entries if entry.name() != name]

    def copy(self):
        copied = []
        for entry in self._entries:
            if isinstance(entry, FakeFolderParmTemplate):
                clone = FakeFolderParmTemplate(entry.name(), entry.label())
                for child in entry.parmTemplates():
                    clone.addParmTemplate(child)
                copied.append(clone)
            else:
                copied.append(entry)
        return FakeParmTemplateGroup(copied)


class FakeText:
    def __init__(self, bindings, runover="layer") -> None:
        self._bindings = bindings
        self._runover = runover

    def oclExtractBindings(self, code):
        return self._bindings

    def oclExtractRunOver(self, code):
        return self._runover


class FakeSession:
    def __init__(self, node, bindings, runover="layer") -> None:
        self.hou = self
        self._node = node
        self.text = FakeText(bindings, runover)
        self.connection = self
        self.modules = self
        self.vexpressionmenu = self

    def node(self, path):
        return self._node if path == self._node.path() else None

    def FloatParmTemplate(self, name, label, num_components, default_value=()):
        return FakeTemplate(name, label, "Float")

    def IntParmTemplate(self, name, label, num_components, default_value=()):
        return FakeTemplate(name, label, "Int")

    def FolderParmTemplate(self, name, label):
        return FakeFolderParmTemplate(name, label)

    def createSpareParmsFromOCLBindings(self, node, parmname):
        folder = FakeFolderParmTemplate(
            "folder_generatedparms_kernelcode",
            "Generated Channel Parameters",
        )
        for binding in self.text._bindings:
            if binding["type"] in {"int", "float", "float2", "float3", "float4"}:
                folder.addParmTemplate(FakeTemplate(binding["name"], binding["name"].title(), "Float"))

        group = node.parmTemplateGroup()
        group.insertBefore("kernelcode", folder)
        node.setParmTemplateGroup(group)


class FakeConnect:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self, host, port):
        class _Ctx:
            def __enter__(inner_self):
                return self.session

            def __exit__(inner_self, exc_type, exc, tb):
                return False

        return _Ctx()


def _binding(**kwargs):
    base = {
        "name": "",
        "type": "float",
        "portname": "",
        "precision": "node",
        "optional": False,
        "defval": False,
        "readable": True,
        "writeable": False,
        "timescale": "none",
        "layertype": "floatn",
        "layerborder": "input",
        "attribute": "",
        "attribclass": "detail",
        "attribtype": "float",
        "attribsize": 1,
        "volume": "",
        "resolution": False,
        "voxelsize": False,
        "xformtoworld": False,
        "xformtovoxel": False,
        "vdbtype": "any",
        "intval": 0,
        "fval": 0.0,
        "v2val": (0.0, 0.0),
        "v3val": (0.0, 0.0, 0.0),
        "v4val": (0.0, 0.0, 0.0, 0.0),
    }
    base.update(kwargs)
    return base


def test_handle_sync_rebuilds_signature_and_bindings(monkeypatch) -> None:
    bindings = [
        _binding(name="src", type="layer", portname="src", readable=True, optional=True),
        _binding(name="dst", type="layer", portname="dst", readable=False, writeable=True),
        _binding(name="gain", type="float", portname="gain", fval=2.0, defval=True),
    ]
    node_obj = FakeOpenclNode()
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings)))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_sync(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/opencl1",
            clear=False,
            bindings_only=False,
        )
    )

    assert result["ok"] is True
    assert node_obj.set_parms_calls[0] == {"bindings": 0}
    assert node_obj.set_parms_calls[1] == {"bindings": 3}
    assert node_obj.set_parms_calls[2]["bindings3_name"] == "gain"
    assert node_obj.set_parms_calls[2]["bindings3_fval"] == 2.0
    assert node_obj.set_parms_calls[3] == {"inputs": 0, "outputs": 0}
    assert node_obj.set_parms_calls[4] == {"inputs": 1, "outputs": 1}
    payload = node_obj.set_parms_calls[5]
    assert payload["input1_name"] == "src"
    assert payload["input1_optional"] is True
    assert payload["output1_name"] == "dst"
    assert node_obj.runover_parm.last_set == "layer"
    assert result["data"]["spare_parms"] == ["gain"]
    assert result["data"]["bindings_only"] is False
    folder = node_obj._group.entries()[0]
    assert folder.name() == "folder_generatedparms_kernelcode"
    assert [child.name() for child in folder.parmTemplates()] == ["gain"]


def test_handle_sync_bindings_only_leaves_signature_untouched(monkeypatch) -> None:
    bindings = [
        _binding(name="src", type="layer", portname="src", readable=True, optional=True),
        _binding(name="dst", type="layer", portname="dst", readable=False, writeable=True),
        _binding(name="gain", type="float", portname="gain", fval=2.0, defval=True),
    ]
    node_obj = FakeOpenclNode()
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings)))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_sync(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/opencl1",
            clear=False,
            bindings_only=True,
        )
    )

    assert result["ok"] is True
    assert node_obj.set_parms_calls[0] == {"bindings": 0}
    assert node_obj.set_parms_calls[1] == {"bindings": 3}
    assert node_obj.set_parms_calls[2]["bindings3_name"] == "gain"
    assert all("inputs" not in payload or payload == {"bindings": 0} for payload in node_obj.set_parms_calls[:3])
    assert len(node_obj.set_parms_calls) == 3
    assert result["data"]["bindings_only"] is True
    assert result["data"]["spare_parms"] == ["gain"]
    assert result["data"]["inputs"] == [{"name": "src", "type": "floatn", "optional": True}]
    assert result["data"]["outputs"] == [{"name": "dst", "type": "floatn"}]


def test_handle_sync_groups_ports_and_preserves_metadata(monkeypatch) -> None:
    bindings = [
        _binding(name="size_ref", type="layer", portname="size_ref", readable=False, writeable=False, optional=True),
        _binding(name="stamp0", type="layer", portname="stamp0", readable=True),
        _binding(name="geoP", type="attribute", portname="geo", attribute="P", attribclass="point", attribsize=3),
        _binding(
            name="geoid",
            type="attribute",
            portname="geo",
            attribute="id",
            attribclass="point",
            attribtype="int",
            optional=True,
        ),
        _binding(name="dst", type="layer", portname="dst", readable=False, writeable=True),
    ]
    node_obj = FakeOpenclNode()
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings, runover="")))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_sync(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/opencl1",
            clear=False,
            bindings_only=False,
        )
    )

    assert result["ok"] is True
    assert result["data"]["inputs"] == [
        {"name": "size_ref", "type": "metadata", "optional": True},
        {"name": "stamp0", "type": "floatn", "optional": False},
        {"name": "geo", "type": "geo", "optional": False},
    ]
    assert result["data"]["outputs"] == [{"name": "dst", "type": "floatn"}]
    signature_payload = node_obj.set_parms_calls[5]
    assert signature_payload["input1_name"] == "size_ref"
    assert signature_payload["input1_type"] == "metadata"
    assert signature_payload["input2_name"] == "stamp0"
    assert signature_payload["input3_name"] == "geo"
    assert signature_payload["input3_type"] == "geo"


def test_handle_sync_preserves_existing_signature_order(monkeypatch) -> None:
    bindings = [
        _binding(name="size_ref", type="layer", portname="size_ref", readable=False, writeable=False, optional=True),
        _binding(name="stamp0", type="layer", portname="stamp0", readable=True),
        _binding(name="stamp1", type="layer", portname="stamp1", readable=True, optional=True),
        _binding(name="cam", type="layer", portname="cam", readable=True),
        _binding(name="geoP", type="attribute", portname="geo", attribute="P", attribclass="point", attribsize=3),
        _binding(name="extra_bias", type="float", portname="extra_bias", fval=0.5, defval=True),
        _binding(name="dst", type="layer", portname="dst", readable=False, writeable=True),
    ]
    node_obj = FakeOpenclNode()
    node_obj.signature_data = {
        "inputs": [
            {"input#_name": "size_ref", "input#_type": "metadata", "input#_optional": True},
            {"input#_name": "stamp0"},
            {"input#_name": "stamp1", "input#_optional": True},
            {"input#_name": "cam"},
            {"input#_name": "geo", "input#_type": "geo"},
        ],
        "outputs": [{"output#_name": "dst"}],
    }
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings, runover="")))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_sync(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/opencl1",
            clear=False,
            bindings_only=False,
        )
    )

    assert result["ok"] is True
    assert result["data"]["inputs"] == [
        {"name": "size_ref", "type": "metadata", "optional": True},
        {"name": "stamp0", "type": "floatn", "optional": False},
        {"name": "stamp1", "type": "floatn", "optional": True},
        {"name": "cam", "type": "floatn", "optional": False},
        {"name": "geo", "type": "geo", "optional": False},
    ]
    signature_payload = node_obj.set_parms_calls[5]
    assert [signature_payload[f"input{i}_name"] for i in range(1, 6)] == [
        "size_ref",
        "stamp0",
        "stamp1",
        "cam",
        "geo",
    ]


def test_signature_type_maps_vdb() -> None:
    assert opencl._signature_type("vdb", {"vdbtype": "float"}, output=False) == "fvdb"
