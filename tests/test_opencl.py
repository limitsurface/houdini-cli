from argparse import Namespace

from houdini_cli.commands import opencl


class FakeParm:
    def __init__(self, value):
        self.value = value
        self.last_set = None
        self.last_expression = None

    def evalAsString(self):
        return self.value

    def set(self, value):
        self.last_set = value

    def setExpression(self, expression):
        self.last_expression = expression

    def expression(self):
        if self.last_expression is None:
            raise RuntimeError("No expression")
        return self.last_expression

    def eval(self):
        return self.value


class FakeOpenclNode:
    def __init__(self) -> None:
        self.set_parms_calls = []
        self.kernel_parm = FakeParm("#bind layer src? val=0\n#bind layer !&dst\n#bind parm gain float val=2\n")
        self.runover_parm = FakeParm("layer")
        self._group = FakeParmTemplateGroup()
        self.signature_data = {"inputs": [{"input#_name": "src", "input#_optional": True}], "outputs": [{"output#_name": "dst"}]}
        self._input_data_types = ["Mono"]
        self._input_connections = []
        self._errors = []
        self._warnings = []
        self._messages = []
        self._parms = {
            "kernelcode": self.kernel_parm,
            "options_runover": self.runover_parm,
            "inputs": FakeParm(1),
            "input1_name": FakeParm("src"),
            "input1_type": FakeParm("floatn"),
            "input1_optional": FakeParm(True),
            "outputs": FakeParm(1),
            "output1_name": FakeParm("dst"),
            "output1_type": FakeParm("floatn"),
            "bindings": FakeParm(0),
        }

    def path(self):
        return "/obj/cops/opencl1"

    def setParms(self, payload):
        self.set_parms_calls.append(payload)
        for key, value in payload.items():
            self._parms.setdefault(key, FakeParm(value)).value = value
        if "inputs" in payload:
            count = int(payload["inputs"])
            self._input_data_types = ["Mono"] * count
            self.signature_data["inputs"] = [{} for _ in range(count)]
        if "outputs" in payload:
            count = int(payload["outputs"])
            self.signature_data["outputs"] = [{} for _ in range(count)]
        for key, value in payload.items():
            if key.startswith("input") and key.endswith("_type"):
                index = int(key[len("input") : key.index("_")]) - 1
                while len(self._input_data_types) <= index:
                    self._input_data_types.append("Mono")
                self._input_data_types[index] = "Geometry" if value == "geo" else "Mono"
                self.signature_data["inputs"][index]["input#_type"] = value
            elif key.startswith("input") and key.endswith("_name"):
                index = int(key[len("input") : key.index("_")]) - 1
                self.signature_data["inputs"][index]["input#_name"] = value
            elif key.startswith("input") and key.endswith("_optional"):
                index = int(key[len("input") : key.index("_")]) - 1
                self.signature_data["inputs"][index]["input#_optional"] = value
            elif key.startswith("output") and key.endswith("_name"):
                index = int(key[len("output") : key.index("_")]) - 1
                self.signature_data["outputs"][index]["output#_name"] = value
            elif key.startswith("output") and key.endswith("_type"):
                index = int(key[len("output") : key.index("_")]) - 1
                self.signature_data["outputs"][index]["output#_type"] = value

    def parm(self, name):
        return self._parms.get(name)

    def parmTemplateGroup(self):
        return self._group.copy()

    def setParmTemplateGroup(self, group):
        self._group = group.copy()

    def parmsAsData(self, brief=False):
        return self.signature_data

    def inputDataTypes(self):
        return tuple(self._input_data_types)

    def inputConnections(self):
        return tuple(self._input_connections)

    def errors(self):
        return tuple(self._errors)

    def warnings(self):
        return tuple(self._warnings)

    def messages(self):
        return tuple(self._messages)

    def setInput(self, index, node, output_index=0):
        self._input_connections = [conn for conn in self._input_connections if conn.inputIndex() != index]
        if node is not None:
            self._input_connections.append(FakeConnection(index, node, output_index))

    def cook(self, force=True):
        return None


class FakeCategory:
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self):
        return self._name


class FakeNodeType:
    def __init__(self, category: str) -> None:
        self._category = FakeCategory(category)

    def category(self):
        return self._category


class FakeSopOpenclNode(FakeOpenclNode):
    def __init__(self) -> None:
        super().__init__()
        self._parms.pop("inputs")
        self._parms.pop("outputs")
        self._parms["runover"] = FakeParm("attribute")

    def path(self):
        return "/obj/geo1/opencl1"

    def type(self):
        return FakeNodeType("Sop")

    def parm(self, name):
        parm = super().parm(name)
        if parm is None and name.startswith("bindings") and "_portname" not in name and "_layerborder" not in name:
            parm = FakeParm("")
            self._parms[name] = parm
        return parm


class FakeDopOpenclNode(FakeOpenclNode):
    def __init__(self) -> None:
        super().__init__()
        self._parms.pop("inputs")
        self._parms.pop("outputs")
        self._parms.pop("bindings")
        self._parms["runover"] = FakeParm("allfields")
        self._parms["paramcount"] = FakeParm(0)

    def path(self):
        return "/obj/dopnet1/gasopencl1"

    def type(self):
        return FakeNodeType("Dop")

    def setParms(self, payload):
        self.set_parms_calls.append(payload)
        for key, value in payload.items():
            self._parms.setdefault(key, FakeParm(value)).value = value

    def parm(self, name):
        parm = super().parm(name)
        if parm is None and name.startswith("parameter"):
            parm = FakeParm("")
            self._parms[name] = parm
        return parm


class FakeSourceNode:
    def __init__(self, path: str, output_types: list[str]) -> None:
        self._path = path
        self._output_types = output_types

    def path(self):
        return self._path

    def outputDataTypes(self):
        return tuple(self._output_types)


class FakeConnection:
    def __init__(self, input_index: int, source_node: FakeSourceNode, output_index: int) -> None:
        self._input_index = input_index
        self._source_node = source_node
        self._output_index = output_index

    def inputIndex(self):
        return self._input_index

    def inputNode(self):
        return self._source_node

    def outputIndex(self):
        return self._output_index

    def outputName(self):
        return f"output{self._output_index + 1}"


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
        "fieldname": "",
        "fieldoffsets": True,
        "geometry": "Geometry",
        "input": 0,
        "dataname": "",
        "optionname": "",
        "optiontype": "float",
        "optionsize": 1,
        "rampsize": 1024,
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
    assert node_obj.set_parms_calls[1] == {"bindings": 1}
    assert node_obj.set_parms_calls[2]["bindings1_name"] == "gain"
    assert node_obj.set_parms_calls[2]["bindings1_fval"] == 2.0
    assert node_obj.parm("bindings1_fval").last_expression == 'ch("./gain")'
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
    assert node_obj.set_parms_calls[1] == {"bindings": 1}
    assert node_obj.set_parms_calls[2]["bindings1_name"] == "gain"
    assert node_obj.parm("bindings1_fval").last_expression == 'ch("./gain")'
    assert all("inputs" not in payload or payload == {"bindings": 0} for payload in node_obj.set_parms_calls[:3])
    assert len(node_obj.set_parms_calls) == 3
    assert result["data"]["bindings_only"] is True
    assert result["data"]["spare_parms"] == ["gain"]
    assert result["data"]["inputs"] == [{"name": "src", "type": "floatn", "optional": True}]
    assert result["data"]["outputs"] == [{"name": "dst", "type": "floatn"}]


def test_handle_sync_sop_rebuilds_all_binding_rows_without_signature(monkeypatch) -> None:
    bindings = [
        _binding(
            name="P",
            type="attribute",
            portname="",
            attribute="P",
            attribclass="point",
            attribsize=3,
            writeable=True,
        ),
        _binding(name="gain", type="float", portname="gain", fval=2.0, defval=True),
    ]
    node_obj = FakeSopOpenclNode()
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings, runover="attribute")))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_sync(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/geo1/opencl1",
            clear=True,
            bindings_only=False,
            disconnect_invalid=False,
            details=True,
        )
    )

    assert result["ok"] is True
    assert result["data"]["context"] == "sop"
    assert result["data"]["inputs"] == []
    assert result["data"]["outputs"] == []
    assert result["data"]["spare_parms"] == ["gain"]
    assert not any("inputs" in payload or "outputs" in payload for payload in node_obj.set_parms_calls)
    assert any(payload == {"bindings": 2} for payload in node_obj.set_parms_calls)
    row_payload = next(payload for payload in node_obj.set_parms_calls if payload.get("bindings1_name") == "P")
    assert row_payload["bindings1_type"] == "attribute"
    assert row_payload["bindings2_name"] == "gain"
    assert result["data"]["validation"]["bindings_match_kernel"] is True
    assert result["data"]["validation"]["signature_matches_kernel"] is None


def test_handle_sync_sop_preserves_binding_input_targets(monkeypatch) -> None:
    bindings = [
        _binding(
            name="P",
            type="attribute",
            portname="",
            attribute="P",
            attribclass="point",
            attribsize=3,
            writeable=True,
            input=0,
        ),
        _binding(
            name="guideP",
            type="attribute",
            portname="",
            attribute="P",
            attribclass="point",
            attribsize=3,
            input=1,
        ),
    ]
    node_obj = FakeSopOpenclNode()
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings, runover="attribute")))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_sync(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/geo1/opencl1",
            clear=True,
            bindings_only=False,
            disconnect_invalid=False,
            details=True,
        )
    )

    assert result["ok"] is True
    row_payload = next(payload for payload in node_obj.set_parms_calls if payload.get("bindings1_name") == "P")
    assert row_payload["bindings1_input"] == 0
    assert row_payload["bindings2_name"] == "guideP"
    assert row_payload["bindings2_input"] == 1


def test_handle_validate_sop_accepts_explicit_rows_without_bind_directives(monkeypatch) -> None:
    node_obj = FakeSopOpenclNode()
    node_obj.kernel_parm.value = "@KERNEL { @P.set(@P); }"
    node_obj.setParms({"bindings": 2})
    node_obj.setParms(
        {
            "bindings1_name": "P",
            "bindings1_type": "attribute",
            "bindings2_name": "guideP",
            "bindings2_type": "attribute",
        }
    )
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, [], runover="attribute")))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_validate(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/geo1/opencl1",
            details=False,
        )
    )

    assert result["ok"] is True
    assert result["data"]["binding_count"] == 2
    assert result["data"]["bindings"] == [
        ["P", "attribute", "input"],
        ["guideP", "attribute", "input"],
    ]
    assert result["data"]["sync_required"] is False


def test_handle_sync_dop_rebuilds_gas_opencl_parameters(monkeypatch) -> None:
    bindings = [
        _binding(
            name="density",
            type="scalarfield",
            fieldname="density",
            fieldoffsets=True,
            readable=True,
            writeable=True,
        ),
        _binding(
            name="geoP",
            type="attribute",
            geometry="Geometry",
            attribute="P",
            attribclass="point",
            attribsize=3,
        ),
        _binding(
            name="scale",
            type="option",
            dataname="Controls",
            optionname="scale",
            optiontype="float",
            optionsize=1,
        ),
        _binding(name="gain", type="float", fval=0.5, defval=True),
    ]
    node_obj = FakeDopOpenclNode()
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings, runover="allfields")))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_sync(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/dopnet1/gasopencl1",
            clear=True,
            bindings_only=False,
            disconnect_invalid=False,
            details=True,
        )
    )

    assert result["ok"] is True
    assert result["data"]["context"] == "dop"
    assert result["data"]["spare_parms"] == ["gain"]
    assert not any("inputs" in payload or "outputs" in payload or "bindings" in payload for payload in node_obj.set_parms_calls)
    assert any(payload == {"paramcount": 4} for payload in node_obj.set_parms_calls)
    row_payload = next(payload for payload in node_obj.set_parms_calls if payload.get("parameter1Name") == "density")
    assert row_payload["parameter1Type"] == "scalarfield"
    assert row_payload["parameter1Field"] == "density"
    assert row_payload["parameter1Output"] is True
    assert row_payload["parameter2Geometry"] == "Geometry"
    assert row_payload["parameter2Attribute"] == "P"
    assert row_payload["parameter3DataName"] == "Controls"
    assert row_payload["parameter3OptionName"] == "scale"
    assert row_payload["parameter4Flt"] == 0.5
    assert node_obj.parm("parameter4Flt").last_expression == 'ch("./gain")'
    assert result["data"]["validation"]["bindings_match_kernel"] is True
    assert result["data"]["validation"]["signature_matches_kernel"] is None


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
            details=True,
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
    signature_payload = next(payload for payload in node_obj.set_parms_calls if payload.get("input1_name") == "size_ref")
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


def test_handle_validate_reports_signature_drift_and_invalid_connection(monkeypatch) -> None:
    bindings = [
        _binding(name="src", type="layer", portname="src", readable=True, optional=False),
        _binding(name="geoP", type="attribute", portname="geo", attribute="P", attribclass="point", attribsize=3),
        _binding(name="dst", type="layer", portname="dst", readable=False, writeable=True),
    ]
    node_obj = FakeOpenclNode()
    node_obj.signature_data = {
        "inputs": [
            {"input#_name": "src", "input#_type": "floatn", "input#_optional": False},
            {"input#_name": "light", "input#_type": "floatn", "input#_optional": False},
        ],
        "outputs": [{"output#_name": "dst", "output#_type": "floatn"}],
    }
    node_obj._parms.update(
        {
            "inputs": FakeParm(2),
            "input1_name": FakeParm("src"),
            "input1_type": FakeParm("floatn"),
            "input1_optional": FakeParm(False),
            "input2_name": FakeParm("light"),
            "input2_type": FakeParm("floatn"),
            "input2_optional": FakeParm(False),
        }
    )
    node_obj._input_data_types = ["Mono", "Geometry"]
    mono_src = FakeSourceNode("/obj/cops/light_alpha", ["Mono"])
    node_obj._input_connections = [
        FakeConnection(0, mono_src, 0),
        FakeConnection(1, mono_src, 0),
    ]
    node_obj._errors = ["Can't convert Mono to Geometry for geo (at signature index 0)"]
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings)))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_validate(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/opencl1",
            details=True,
        )
    )

    assert result["ok"] is True
    data = result["data"]
    assert data["signature_matches_kernel"] is False
    assert data["sync_required"] is True
    assert any("opencl sync" in hint for hint in data["hints"])
    assert data["invalid_connection_count"] == 1
    assert data["errors"] == ["Can't convert Mono to Geometry for geo (at signature index 0)"]
    assert data["inputs"][1]["expected_data_type"] == "Geometry"
    assert data["inputs"][1]["source_output_type"] == "Mono"
    assert data["inputs"][1]["compatible"] is False


def test_handle_validate_reports_stale_opencl_binding_rows(monkeypatch) -> None:
    bindings = [
        _binding(name="src", type="layer", portname="src", readable=True, optional=False),
        _binding(name="dst", type="layer", portname="dst", readable=False, writeable=True),
        _binding(name="gain", type="float", portname="gain", fval=2.0, defval=True),
    ]
    node_obj = FakeOpenclNode()
    node_obj.setParms({"bindings": 3})
    node_obj.setParms(
        {
            "bindings1_name": "src",
            "bindings1_type": "layer",
            "bindings2_name": "dst",
            "bindings2_type": "layer",
            "bindings3_name": "gain",
            "bindings3_type": "float",
            "bindings3_fval": 2.0,
        }
    )
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings)))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_validate(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/opencl1",
        )
    )

    assert result["ok"] is True
    hints = result["data"]["hints"]
    assert any("layer bindings" in hint and "src" in hint and "dst" in hint for hint in hints)
    assert any("not linked to generated spare parms" in hint and "gain" in hint for hint in hints)


def test_handle_validate_accepts_vector_spare_parm_axis_suffixes(monkeypatch) -> None:
    bindings = [
        _binding(name="manual_num", type="float4", portname="manual_num", defval=True),
        _binding(name="manual_den", type="float3", portname="manual_den", defval=True),
    ]
    node_obj = FakeOpenclNode()
    node_obj.setParms(
        {
            "bindings": 2,
            "bindings1_name": "manual_num",
            "bindings1_type": "float4",
            "bindings2_name": "manual_den",
            "bindings2_type": "float3",
        }
    )
    for suffix, parm_name in zip("xyzw", ("bindings1_v4val1", "bindings1_v4val2", "bindings1_v4val3", "bindings1_v4val4")):
        node_obj._parms[parm_name] = FakeParm(0.0)
        node_obj._parms[parm_name].setExpression(f'ch("./manual_num{suffix}")')
    for suffix, parm_name in zip("xyz", ("bindings2_v3val1", "bindings2_v3val2", "bindings2_v3val3")):
        node_obj._parms[parm_name] = FakeParm(0.0)
        node_obj._parms[parm_name].setExpression(f'ch("./manual_den{suffix}")')
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings)))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_validate(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/opencl1",
        )
    )

    assert result["ok"] is True
    assert not any("not linked to generated spare parms" in hint for hint in result["data"]["hints"])


def test_handle_sync_can_disconnect_invalid_inputs(monkeypatch) -> None:
    bindings = [
        _binding(name="src", type="layer", portname="src", readable=True, optional=False),
        _binding(name="geoP", type="attribute", portname="geo", attribute="P", attribclass="point", attribsize=3),
        _binding(name="dst", type="layer", portname="dst", readable=False, writeable=True),
    ]
    node_obj = FakeOpenclNode()
    mono_src = FakeSourceNode("/obj/cops/light_alpha", ["Mono"])
    node_obj._input_connections = [
        FakeConnection(0, mono_src, 0),
        FakeConnection(1, mono_src, 0),
    ]
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings)))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_sync(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/opencl1",
            clear=True,
            bindings_only=False,
            disconnect_invalid=True,
            details=True,
        )
    )

    assert result["ok"] is True
    data = result["data"]
    assert data["disconnect_invalid"] is True
    assert data["disconnected_inputs"] == [1]
    assert data["validation"]["invalid_connection_count"] == 0
    assert data["validation"]["inputs"][1]["connected"] is False


def test_handle_validate_compact_response_keeps_binding_names(monkeypatch) -> None:
    bindings = [
        _binding(name="src", type="layer", portname="src", readable=True),
        _binding(name="dst", type="layer", portname="dst", readable=False, writeable=True),
        _binding(name="gain", type="float", portname="gain", fval=2.0, defval=True),
    ]
    node_obj = FakeOpenclNode()
    monkeypatch.setattr(opencl, "connect", FakeConnect(FakeSession(node_obj, bindings)))
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    result = opencl.handle_validate(
        Namespace(host="localhost", port=18811, node_path="/obj/cops/opencl1", details=False)
    )

    assert result["data"]["binding_cols"] == ["name", "type", "direction"]
    assert result["data"]["bindings"] == [
        ["src", "layer", "input"],
        ["dst", "layer", "output"],
        ["gain", "float", "parm"],
    ]
    assert "desired_inputs" not in result["data"]


def test_existing_signature_unwraps_parms_as_data_values(monkeypatch) -> None:
    node_obj = FakeOpenclNode()
    node_obj.signature_data = {
        "inputs": [
            {
                "input#_name": {"value": "src"},
                "input#_type": {"value": "floatn"},
                "input#_optional": {"value": False},
            }
        ],
        "outputs": [{"output#_name": {"value": "dst"}, "output#_type": {"value": "floatn"}}],
    }
    node_obj._parms.pop("inputs")
    node_obj._parms.pop("outputs")
    monkeypatch.setattr(opencl, "localize", lambda value: value)

    assert opencl._existing_signature_entries(node_obj, output=False) == [
        {"name": "src", "type": "floatn", "optional": False}
    ]
    assert opencl._existing_signature_entries(node_obj, output=True) == [
        {"name": "dst", "type": "floatn", "optional": False}
    ]
