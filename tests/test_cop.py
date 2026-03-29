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


class FakeCopNode:
    def path(self):
        return "/obj/cops/constant1"

    def outputNames(self):
        return ("constant",)

    def outputLabels(self):
        return ("Constant",)

    def layer(self, output_index=0):
        assert output_index == 0
        return FakeLayer()


class FakeSession:
    def __init__(self, node):
        self.hou = self
        self._node = node

    def node(self, path):
        return self._node if path == self._node.path() else None


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
