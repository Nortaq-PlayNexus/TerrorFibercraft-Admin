import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nexus_vision.adapters import DetectorAdapter, ModelRegistry, OcrAdapter
from nexus_vision.model import DetectedObject, ScreenState


class FakeFrame:
    def __init__(self, annotations, ocr_regions=None):
        self.annotations = annotations
        self.ocr_regions = ocr_regions or []


def test_synthetic_detector():
    d = DetectorAdapter(model_path=None)
    assert d.available()
    frame = FakeFrame([("rex", 0.9, (0, 0, 10, 10))])
    assert d.detect(frame) == [("rex", 0.9, (0, 0, 10, 10))]


def test_synthetic_ocr():
    o = OcrAdapter()
    assert not o.available()  # no backend loaded
    assert o.read(FakeFrame(None)) == []


def test_registry_roundtrip():
    r = ModelRegistry()
    d = DetectorAdapter()
    r.register("yolo-ark-v3", d)
    assert "yolo-ark-v3" in r.available_ids()
    assert r.get("yolo-ark-v3") is d
    assert r.get("missing") is None


def test_screen_state_snapshot_json_shape():
    s = ScreenState(captured_at_ms=1234)
    s.objects = [DetectedObject(track_id=1, class_name="rex", confidence=0.9, bbox=(0, 0, 5, 5))]
    snap = s.snapshot(now_ms=9999)
    assert snap["captured_at_ms"] == 9999
    assert snap["schema"] == 3
    assert snap["objects"][0]["class"] == "rex"
    assert snap["objects"][0]["bbox"] == [0, 0, 5, 5]
    assert "hud" in snap and "player" in snap
