import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nexus_vision.query import Predicate, evaluate_query
from nexus_vision.model import ScreenState, DetectedObject


def obj(cls, conf, seen_ms_ago, now):
    return DetectedObject(
        track_id=1, class_name=cls, confidence=conf,
        bbox=(0, 0, 10, 10), last_seen_ms=now - seen_ms_ago,
    )


def test_any_matches():
    s = ScreenState(captured_at_ms=1000, objects=[obj("metal_node", 0.9, 100, 1000)])
    res = evaluate_query(s, "any", [Predicate("metal_node")])
    assert len(res) == 1


def test_any_absent_fails():
    s = ScreenState(captured_at_ms=1000, objects=[])
    assert evaluate_query(s, "any", [Predicate("rex")]) == []


def test_stale_excluded():
    s = ScreenState(captured_at_ms=9000, objects=[obj("rex", 0.9, 9000, 9000)])
    assert evaluate_query(s, "any", [Predicate("rex", max_stale_ms=2000)]) == []


def test_low_conf_excluded():
    s = ScreenState(captured_at_ms=1000, objects=[obj("rex", 0.3, 100, 1000)])
    assert evaluate_query(s, "any", [Predicate("rex", min_conf=0.5)]) == []


def test_none_passes_when_clear():
    s = ScreenState(captured_at_ms=1000, objects=[obj("metal_node", 0.9, 100, 1000)])
    res = evaluate_query(s, "none", [Predicate("rex")])
    assert res == []


def test_all_requires_every():
    s = ScreenState(
        captured_at_ms=1000,
        objects=[obj("metal_node", 0.9, 100, 1000), obj("anky", 0.8, 100, 1000)],
    )
    res = evaluate_query(s, "all", [Predicate("metal_node"), Predicate("anky")])
    assert len(res) == 2
