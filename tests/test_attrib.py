from argparse import Namespace

import pytest

from houdini_cli.commands import attrib


class FakeAttrib:
    def __init__(self, name, size=1, data_type="attribData.Float", array=False) -> None:
        self._name = name
        self._size = size
        self._data_type = data_type
        self._array = array

    def name(self):
        return self._name

    def size(self):
        return self._size

    def dataType(self):
        return self._data_type

    def isArrayType(self):
        return self._array


class FakeElement:
    def __init__(self, values) -> None:
        self.values = values

    def attribValue(self, attrib_obj):
        return self.values[attrib_obj.name()]


class FakePrim(FakeElement):
    def __init__(self, values, vertices) -> None:
        super().__init__(values)
        self._vertices = vertices

    def vertices(self):
        return self._vertices


class FakeGeometry:
    def __init__(self) -> None:
        self._point_attribs = [FakeAttrib("P", size=3), FakeAttrib("Cd", size=3)]
        self._prim_attribs = [FakeAttrib("name", data_type="attribData.String")]
        self._vertex_attribs = [FakeAttrib("uv", size=2)]
        self._detail_attribs = [FakeAttrib("iteration", data_type="attribData.Int")]

        self._points = [
            FakeElement({"P": [0.0, 0.0, 0.0], "Cd": [1.0, 0.0, 0.0]}),
            FakeElement({"P": [1.0, 0.0, 0.0], "Cd": [0.0, 1.0, 0.0]}),
            FakeElement({"P": [2.0, 0.0, 0.0], "Cd": [0.0, 0.0, 1.0]}),
        ]
        self._prims = [
            FakePrim({"name": "a"}, [FakeElement({"uv": [0.1, 0.2]}), FakeElement({"uv": [0.3, 0.4]})]),
            FakePrim({"name": "b"}, [FakeElement({"uv": [0.5, 0.6]})]),
        ]
        self._detail_values = {"iteration": 7}

    def pointAttribs(self):
        return self._point_attribs

    def primAttribs(self):
        return self._prim_attribs

    def vertexAttribs(self):
        return self._vertex_attribs

    def globalAttribs(self):
        return self._detail_attribs

    def findPointAttrib(self, name):
        return next((attrib_obj for attrib_obj in self._point_attribs if attrib_obj.name() == name), None)

    def findPrimAttrib(self, name):
        return next((attrib_obj for attrib_obj in self._prim_attribs if attrib_obj.name() == name), None)

    def findVertexAttrib(self, name):
        return next((attrib_obj for attrib_obj in self._vertex_attribs if attrib_obj.name() == name), None)

    def findGlobalAttrib(self, name):
        return next((attrib_obj for attrib_obj in self._detail_attribs if attrib_obj.name() == name), None)

    def pointCount(self):
        return len(self._points)

    def primCount(self):
        return len(self._prims)

    def vertexCount(self):
        return sum(len(prim.vertices()) for prim in self._prims)

    def iterPoints(self):
        return self._points

    def iterPrims(self):
        return self._prims

    def attribValue(self, attrib_obj):
        return self._detail_values[attrib_obj.name()]


class FakeNode:
    def __init__(self, geometry=None, path="/obj/geo1/OUT") -> None:
        self._geometry = geometry
        self._path = path

    def geometry(self):
        return self._geometry

    def path(self):
        return self._path


class FakeSession:
    def __init__(self, node_map) -> None:
        self.hou = self
        self.node_map = node_map

    def node(self, path):
        return self.node_map.get(path)


class FakeConnect:
    def __init__(self, fake_session: FakeSession) -> None:
        self.fake_session = fake_session

    def __call__(self, host, port):
        class _Ctx:
            def __enter__(inner_self):
                return self.fake_session

            def __exit__(inner_self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_handle_list_all_classes(monkeypatch) -> None:
    geometry = FakeGeometry()
    monkeypatch.setattr(attrib, "connect", FakeConnect(FakeSession({"/obj/geo1/OUT": FakeNode(geometry)})))
    monkeypatch.setattr(attrib, "localize", lambda value: value)

    result = attrib.handle_list(Namespace(host="localhost", port=18811, node_path="/obj/geo1/OUT", attrib_class=None))

    assert result["ok"] is True
    assert "point" in result["data"]["classes"]
    assert result["data"]["classes"]["point"][0]["name"] == "P"
    assert result["data"]["classes"]["detail"][0]["data_type"] == "int"


def test_handle_get_sampled_values(monkeypatch) -> None:
    geometry = FakeGeometry()
    monkeypatch.setattr(attrib, "connect", FakeConnect(FakeSession({"/obj/geo1/OUT": FakeNode(geometry)})))
    monkeypatch.setattr(attrib, "localize", lambda value: value)

    result = attrib.handle_get(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/geo1/OUT",
            attrib_name="Cd",
            attrib_class="point",
            element=None,
            limit=2,
            stats=None,
        )
    )

    assert result["ok"] is True
    assert len(result["data"]["values"]) == 2
    assert result["meta"] == {"limit": 2, "truncated": True, "total_elements": 3}


def test_handle_get_specific_element(monkeypatch) -> None:
    geometry = FakeGeometry()
    monkeypatch.setattr(attrib, "connect", FakeConnect(FakeSession({"/obj/geo1/OUT": FakeNode(geometry)})))
    monkeypatch.setattr(attrib, "localize", lambda value: value)

    result = attrib.handle_get(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/geo1/OUT",
            attrib_name="Cd",
            attrib_class="point",
            element=1,
            limit=10,
            stats=None,
        )
    )

    assert result["ok"] is True
    assert result["data"]["value"] == {"element": 1, "value": [0.0, 1.0, 0.0]}
    assert "meta" not in result


def test_handle_get_detail_value(monkeypatch) -> None:
    geometry = FakeGeometry()
    monkeypatch.setattr(attrib, "connect", FakeConnect(FakeSession({"/obj/geo1/OUT": FakeNode(geometry)})))
    monkeypatch.setattr(attrib, "localize", lambda value: value)

    result = attrib.handle_get(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/geo1/OUT",
            attrib_name="iteration",
            attrib_class="detail",
            element=None,
            limit=10,
            stats="min,max",
        )
    )

    assert result["ok"] is True
    assert result["data"]["value"] == 7
    assert result["data"]["stats"] == {"min": 7.0, "max": 7.0}


def test_handle_get_numeric_stats(monkeypatch) -> None:
    geometry = FakeGeometry()
    monkeypatch.setattr(attrib, "connect", FakeConnect(FakeSession({"/obj/geo1/OUT": FakeNode(geometry)})))
    monkeypatch.setattr(attrib, "localize", lambda value: value)

    result = attrib.handle_get(
        Namespace(
            host="localhost",
            port=18811,
            node_path="/obj/geo1/OUT",
            attrib_name="P",
            attrib_class="point",
            element=None,
            limit=2,
            stats="min,max,mean,median",
        )
    )

    assert result["ok"] is True
    assert result["data"]["stats"]["min"] == [0.0, 0.0, 0.0]
    assert result["data"]["stats"]["max"] == [2.0, 0.0, 0.0]
    assert result["data"]["stats"]["mean"] == [1.0, 0.0, 0.0]
    assert result["data"]["stats"]["median"] == [1.0, 0.0, 0.0]


def test_handle_get_rejects_non_numeric_stats(monkeypatch) -> None:
    geometry = FakeGeometry()
    monkeypatch.setattr(attrib, "connect", FakeConnect(FakeSession({"/obj/geo1/OUT": FakeNode(geometry)})))
    monkeypatch.setattr(attrib, "localize", lambda value: value)

    with pytest.raises(ValueError, match="numeric attributes"):
        attrib.handle_get(
            Namespace(
                host="localhost",
                port=18811,
                node_path="/obj/geo1/OUT",
                attrib_name="name",
                attrib_class="prim",
                element=None,
                limit=10,
                stats="min",
            )
        )


def test_handle_get_rejects_detail_element(monkeypatch) -> None:
    geometry = FakeGeometry()
    monkeypatch.setattr(attrib, "connect", FakeConnect(FakeSession({"/obj/geo1/OUT": FakeNode(geometry)})))
    monkeypatch.setattr(attrib, "localize", lambda value: value)

    with pytest.raises(ValueError, match="Detail attributes do not accept --element"):
        attrib.handle_get(
            Namespace(
                host="localhost",
                port=18811,
                node_path="/obj/geo1/OUT",
                attrib_name="iteration",
                attrib_class="detail",
                element=0,
                limit=10,
                stats=None,
            )
        )


def test_handle_get_missing_geometry(monkeypatch) -> None:
    monkeypatch.setattr(attrib, "connect", FakeConnect(FakeSession({"/obj/geo1/OUT": FakeNode(None)})))
    monkeypatch.setattr(attrib, "localize", lambda value: value)

    with pytest.raises(ValueError, match="cooked geometry"):
        attrib.handle_list(Namespace(host="localhost", port=18811, node_path="/obj/geo1/OUT", attrib_class=None))
