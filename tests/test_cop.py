from argparse import Namespace

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
    def __init__(self) -> None:
        self._input_connections = ()
        self._outputs = ()

    def path(self):
        return "/obj/cops/constant1"

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

    def node(self, path):
        return self._nodes.get(path)


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
