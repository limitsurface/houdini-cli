from argparse import Namespace
from types import SimpleNamespace
import os

import pytest

from houdini_cli.commands import cop


class FakeRect:
    def __init__(self, min_x=0, min_y=0, width=4, height=3) -> None:
        self._min_x = min_x
        self._min_y = min_y
        self._width = width
        self._height = height

    def min(self):
        return (self._min_x, self._min_y)

    def max(self):
        return (self._min_x + self._width, self._min_y + self._height)

    def size(self):
        return (self._width, self._height)


class FakeLayer:
    def bufferResolution(self):
        return (4, 3)

    def dataWindow(self):
        return FakeRect()

    def displayWindow(self):
        return FakeRect()

    def pixelScale(self):
        return (1.0, 1.0)

    def pixelAspectRatio(self):
        return 1.0

    def channelCount(self):
        return 3

    def storageType(self):
        return "imageLayerStorageType.Float32"

    def border(self):
        return "imageLayerBorder.Wrap"

    def typeInfo(self):
        return "imageLayerTypeInfo.Color"

    def isConstant(self):
        return False

    def onCPU(self):
        return True

    def onGPU(self):
        return False

    def storesIntegers(self):
        return False

    def pixelToBuffer(self, point):
        return point

    def bufferIndex(self, x, y):
        return (float(x), float(y), 1.0)

    def cameraPosition(self):
        return (0.0, 0.0, 1.0)

    def projection(self):
        return "imageLayerProjection.Orthographic"

    def focalLength(self):
        return 10.4775

    def aperture(self):
        return 20.955

    def clippingRange(self):
        return (0.0, 2.0)


class FakeParmTemplate:
    def __init__(self, menu_items=()) -> None:
        self._menu_items = tuple(menu_items)

    def menuItems(self):
        return self._menu_items


class FakeParm:
    def __init__(self, value=None, menu_items=(), on_press=None) -> None:
        self.value = value
        self.set_values = []
        self._template = FakeParmTemplate(menu_items)
        self._on_press = on_press
        self.pressed = False

    def set(self, value):
        self.value = value
        self.set_values.append(value)

    def eval(self):
        return self.value

    def parmTemplate(self):
        return self._template

    def pressButton(self):
        self.pressed = True
        if self._on_press is not None:
            self._on_press()


class FakeRopNode:
    def __init__(self, parent, name) -> None:
        self._parent = parent
        self._name = name
        self.destroyed = False
        self.parms_by_name = {
            "coppath": FakeParm(""),
            "copoutput": FakeParm(""),
            "colorconversion": FakeParm(0, ("ocio", "bakeocio", "raw")),
            "mkpath": FakeParm(0),
            "outputaovs": FakeParm(0),
            "aov1": FakeParm("C"),
            "useport1": FakeParm(0),
            "port1": FakeParm(0),
            "ociodisplay": FakeParm("Default"),
            "ocioview": FakeParm("Default"),
            "execute": FakeParm(on_press=self._render),
        }

    def _render(self):
        output_path = self.parms_by_name["copoutput"].value
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as handle:
            handle.write(b"fake image")

    def path(self):
        return f"{self._parent.path()}/{self._name}"

    def parm(self, name):
        return self.parms_by_name.get(name)

    def destroy(self):
        self.destroyed = True


class FakeFileNode:
    def __init__(self, parent, name) -> None:
        self._parent = parent
        self._name = name
        self.display = False
        self.render = False
        self.parms_by_name = {
            "filename": FakeParm(""),
            "colorspace": FakeParm(0, ("ocio", "raw")),
            "reload": FakeParm(),
            "addaovs": FakeParm(),
        }

    def path(self):
        return f"{self._parent.path()}/{self._name}"

    def name(self):
        return self._name

    def parm(self, name):
        return self.parms_by_name.get(name)

    def outputNames(self):
        return ("C",)

    def outputLabels(self):
        return ("C",)

    def outputDataTypes(self):
        return ("RGBA",)

    def layer(self, output_index=0):
        assert output_index == 0
        return FakeLayer()

    def setDisplayFlag(self, value):
        self.display = value

    def setRenderFlag(self, value):
        self.render = value


class FakeCopParent:
    def __init__(self, path="/obj/cops") -> None:
        self._path = path
        self.created_nodes = []
        self._children = {}

    def path(self):
        return self._path

    def node(self, name):
        return self._children.get(name)

    def createNode(self, node_type, name=None):
        node_name = name or node_type
        if node_type == "rop_image":
            node = FakeRopNode(self, node_name)
        elif node_type == "file":
            node = FakeFileNode(self, node_name)
        else:
            raise AssertionError(f"Unexpected node type: {node_type}")
        self.created_nodes.append(node)
        self._children[node_name] = node
        return node


class FakeConnection:
    def __init__(self, source_node, output_index=0, output_name="output1", output_label="output1"):
        self._source_node = source_node
        self._output_index = output_index
        self._output_name = output_name
        self._output_label = output_label

    def inputNode(self):
        return self._source_node

    def outputIndex(self):
        return self._output_index

    def outputName(self):
        return self._output_name

    def outputLabel(self):
        return self._output_label


class FakeCopNode:
    def __init__(self, parent=None) -> None:
        self._input_connections = ()
        self._outputs = ()
        self._parent = parent or FakeCopParent()

    def path(self):
        return "/obj/cops/constant1"

    def name(self):
        return "constant1"

    def parent(self):
        return self._parent

    def outputNames(self):
        return ("constant",)

    def outputLabels(self):
        return ("Constant",)

    def outputDataTypes(self):
        return ("Mono",)

    def layer(self, output_index=0):
        assert output_index == 0
        return FakeLayer()

    def inputConnections(self):
        return self._input_connections

    def outputs(self):
        return self._outputs


class FakeOutputProxyNode(FakeCopNode):
    def __init__(self, path, source_node, source_output_index, source_output_name, source_output_label):
        super().__init__()
        self._path = path
        self._input_connections = (
            FakeConnection(
                source_node,
                output_index=source_output_index,
                output_name=source_output_name,
                output_label=source_output_label,
            ),
        )

    def path(self):
        return self._path


class FakeMultiOutputCopNode(FakeCopNode):
    def __init__(self):
        super().__init__()
        self._proxy0 = FakeOutputProxyNode("/obj/cops/geo_alpha", self, 0, "output1", "intrinsic:alpha")
        self._proxy1 = FakeOutputProxyNode("/obj/cops/geo_depth", self, 1, "output2", "intrinsic:depth_eye")
        self._proxy2 = FakeOutputProxyNode("/obj/cops/geo_id", self, 2, "output3", "id")
        self._outputs = (self._proxy0, self._proxy1, self._proxy2)

    def path(self):
        return "/obj/cops/rasterizegeo1"

    def outputNames(self):
        return ("output1", "output2", "output3")

    def outputLabels(self):
        return ("intrinsic:alpha", "intrinsic:depth_eye", "id")

    def outputDataTypes(self):
        return ("Mono", "Mono", "ID")


class FakeSession:
    def __init__(self, *nodes):
        self.hou = self
        self._nodes = {node.path(): node for node in nodes}
        self.connection = SimpleNamespace(modules=SimpleNamespace(os=os, tempfile=SimpleNamespace(gettempdir=lambda: os.getcwd())))

    def node(self, path):
        return self._nodes.get(path)

    def getenv(self, name):
        values = {"JOB": "", "HIP": os.getcwd()}
        return values.get(name, "")

    def expandString(self, value):
        return value.replace("$HIP", os.getcwd())

    def frame(self):
        return 1.0


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


def test_handle_sample_single_point(monkeypatch) -> None:
    monkeypatch.setattr(cop, "connect", FakeConnect(FakeSession(FakeCopNode())))
    monkeypatch.setattr(cop, "localize", lambda value: value)

    result = cop.handle_sample(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/constant1",
            output="0",
            points=None,
            x=2,
            y=1,
        )
    )

    assert result["ok"] is True
    assert result["data"]["output_name"] == "constant"
    assert result["data"]["samples"] == [
        {"x": 2, "y": 1, "buffer_x": 2, "buffer_y": 1, "value": (2.0, 1.0, 1.0)}
    ]


def test_handle_sample_points_json(monkeypatch) -> None:
    monkeypatch.setattr(cop, "connect", FakeConnect(FakeSession(FakeCopNode())))
    monkeypatch.setattr(cop, "localize", lambda value: value)
    monkeypatch.setattr(cop, "load_json_input", lambda raw: [{"x": 0, "y": 0}, {"x": 3, "y": 2}])

    result = cop.handle_sample(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/constant1",
            output="constant",
            points="[]",
            x=None,
            y=None,
        )
    )

    assert result["ok"] is True
    assert len(result["data"]["samples"]) == 2


def test_handle_sample_rejects_out_of_bounds(monkeypatch) -> None:
    monkeypatch.setattr(cop, "connect", FakeConnect(FakeSession(FakeCopNode())))
    monkeypatch.setattr(cop, "localize", lambda value: value)

    with pytest.raises(ValueError, match="outside the layer buffer"):
        cop.handle_sample(
            Namespace(
                host="localhost",
                port=18811,
                node_path="/obj/cops/constant1",
                output="0",
                points=None,
                x=10,
                y=1,
            )
        )


def test_handle_info_single_output(monkeypatch) -> None:
    monkeypatch.setattr(cop, "connect", FakeConnect(FakeSession(FakeCopNode())))
    monkeypatch.setattr(cop, "localize", lambda value: value)

    result = cop.handle_info(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/constant1",
            output=None,
        )
    )

    assert result["ok"] is True
    assert result["data"]["node_path"] == "/obj/cops/constant1"
    assert result["data"]["layer_node_path"] == "/obj/cops/constant1"
    assert result["data"]["source_node_path"] == "/obj/cops/constant1"
    assert result["data"]["output_name"] == "constant"


def test_handle_info_multi_output_direct_node(monkeypatch) -> None:
    multi = FakeMultiOutputCopNode()
    monkeypatch.setattr(cop, "connect", FakeConnect(FakeSession(multi, *multi.outputs())))
    monkeypatch.setattr(cop, "localize", lambda value: value)

    result = cop.handle_info(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/rasterizegeo1",
            output="1",
        )
    )

    assert result["ok"] is True
    assert result["data"]["node_path"] == "/obj/cops/rasterizegeo1"
    assert result["data"]["layer_node_path"] == "/obj/cops/geo_depth"
    assert result["data"]["source_node_path"] == "/obj/cops/rasterizegeo1"
    assert result["data"]["output_index"] == 1
    assert result["data"]["output_label"] == "intrinsic:depth_eye"
    assert result["data"]["output_data_type"] == "Mono"


def test_handle_info_output_proxy_infers_upstream_output(monkeypatch) -> None:
    multi = FakeMultiOutputCopNode()
    proxy = multi.outputs()[2]
    monkeypatch.setattr(cop, "connect", FakeConnect(FakeSession(multi, *multi.outputs())))
    monkeypatch.setattr(cop, "localize", lambda value: value)

    result = cop.handle_info(
        Namespace(
            host="localhost",
            port=18811,
            node_path=proxy.path(),
            output=None,
        )
    )

    assert result["ok"] is True
    assert result["data"]["node_path"] == "/obj/cops/geo_id"
    assert result["data"]["layer_node_path"] == "/obj/cops/geo_id"
    assert result["data"]["source_node_path"] == "/obj/cops/rasterizegeo1"
    assert result["data"]["output_index"] == 2
    assert result["data"]["output_label"] == "id"


def test_handle_export_image_raw_writes_default_file(monkeypatch, tmp_path) -> None:
    parent = FakeCopParent(str(tmp_path / "cops"))
    node = FakeCopNode(parent=parent)
    session = FakeSession(node)
    session.getcwd = str(tmp_path)
    monkeypatch.setattr(cop, "connect", FakeConnect(session))
    monkeypatch.setattr(cop, "localize", lambda value: value)
    monkeypatch.chdir(tmp_path)

    result = cop.handle_export_image(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/cops/constant1",
            mode="raw",
            output=None,
            aov=None,
            display=None,
            view=None,
        )
    )

    rop = parent.created_nodes[0]
    assert result["ok"] is True
    assert result["data"]["mode"] == "raw"
    assert result["data"]["file"]["path"].endswith("constant1_raw_f0001.exr")
    assert os.path.exists(result["data"]["file"]["path"])
    assert rop.parms_by_name["colorconversion"].value == 2
    assert rop.parms_by_name["execute"].pressed is True
    assert rop.destroyed is True


def test_handle_import_image_creates_file_cop(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "tex" / "cli_images" / "edit.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake image")
    parent = FakeCopParent("/obj/cops")
    session = FakeSession(parent)
    monkeypatch.setattr(cop, "connect", FakeConnect(session))
    monkeypatch.setattr(cop, "localize", lambda value: value)
    monkeypatch.chdir(tmp_path)

    result = cop.handle_import_image(
        Namespace(
            host="localhost",
            port=18811,
            image_path=str(image_path),
            parent="/obj/cops",
            name=None,
            colorspace="raw",
            set_display=True,
        )
    )

    file_node = parent.created_nodes[0]
    assert result["ok"] is True
    assert result["data"]["node_path"].endswith("/cli_image_edit")
    assert result["data"]["colorspace"] == "raw"
    assert result["data"]["file"]["parameter_value"].startswith("$HIP/")
    assert file_node.parms_by_name["colorspace"].value == 1
    assert file_node.parms_by_name["reload"].pressed is True
    assert file_node.parms_by_name["addaovs"].pressed is True
    assert file_node.display is True
    assert file_node.render is True
