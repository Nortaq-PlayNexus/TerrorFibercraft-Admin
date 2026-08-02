import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nexus_vision.pipeline import TemporalTracker


def test_iou_perfect_overlap():
    a = (0, 0, 100, 100)
    b = (0, 0, 100, 100)
    assert TemporalTracker.iou(a, b) == 1.0


def test_iou_partial():
    a = (0, 0, 100, 100)
    b = (50, 50, 100, 100)
    assert abs(TemporalTracker.iou(a, b) - 2500.0 / 17500.0) < 1e-9


def test_iou_no_overlap():
    a = (0, 0, 10, 10)
    b = (200, 200, 10, 10)
    assert TemporalTracker.iou(a, b) == 0.0


def test_stable_track_ids():
    t = TemporalTracker()
    t.update([("rex", 0.9, (0, 0, 100, 100))], 1000)
    t.update([("rex", 0.9, (5, 5, 100, 100))], 1100)
    snap = t.snapshot()
    assert len(snap) == 1
    assert snap[0].track_id == 1


def test_different_classes_get_separate_tracks():
    t = TemporalTracker()
    t.update([("rex", 0.9, (0, 0, 100, 100))], 1000)
    t.update([("metal_node", 0.8, (300, 300, 20, 20))], 1100)
    assert len(t.snapshot()) == 2


def test_stale_tracks_age_out():
    t = TemporalTracker(max_age_ms=5000)
    t.update([("rex", 0.9, (0, 0, 100, 100))], 1000)
    t.update([], 9000)
    assert t.snapshot() == []


def test_fresh_filter():
    t = TemporalTracker()
    t.update([("rex", 0.9, (0, 0, 100, 100))], 1000)
    fresh = t.fresh("rex", now_ms=1200, max_stale=2000)
    assert len(fresh) == 1
    stale = t.fresh("rex", now_ms=5000, max_stale=2000)
    assert len(stale) == 0
