import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nexus_vision.pipeline import VisionPipeline
from nexus_vision.model import OcrRegion


def test_ingest_produces_screen_state():
    p = VisionPipeline()
    now = 1_000_000
    state = p.ingest_frame(frame=None, detections=[("metal_node", 0.9, (10, 10, 20, 20))], now_ms=now)
    assert state.captured_at_ms == now
    assert len(state.objects) == 1
    assert state.objects[0].class_name == "metal_node"


def test_ocr_runs_periodically():
    class FakeOcr:
        def __init__(self):
            self.calls = 0

        def read(self, frame):
            self.calls += 1
            return [OcrRegion(bbox=(0, 0, 10, 10), text="Metal", confidence=0.99, kind="item_name")]

    p = VisionPipeline()
    p.ocr_engine = FakeOcr()
    p.ingest_frame(None, [], 1000)
    # ocr runs every 10th frame
    for i in range(9):
        p.ingest_frame(None, [], 2000 + i)
    assert p.ocr_engine.calls >= 1
    assert len(p.ocr) >= 1


def test_player_hud_passthrough():
    p = VisionPipeline()
    p.player.hp = 0.5
    p.hud.taming_percent = 0.42
    state = p.ingest_frame(None, [], 1000)
    assert state.player.hp == 0.5
    assert state.hud.taming_percent == 0.42
