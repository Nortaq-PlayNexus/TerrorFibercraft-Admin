"""NexusScript runtime bridge + vision query evaluation in Python.

The sidecar exposes a query API equivalent to crates/nexus-vision query.rs
so agents/scripts can ask "is a metal node near the player" over the same
semantics as the Rust core.
"""
from __future__ import annotations

from .model import ScreenState


class Predicate:
    def __init__(self, class_name: str, min_conf: float = 0.5, max_stale_ms: int = 2000):
        self.class_name = class_name
        self.min_conf = min_conf
        self.max_stale_ms = max_stale_ms


def evaluate_query(state: ScreenState, op: str, preds: list[Predicate]) -> list:
    """op: 'any' | 'all' | 'none'. Returns matched objects (or [] for none-op)."""
    now = state.captured_at_ms

    def match(p: Predicate) -> list:
        return [
            o for o in state.objects
            if o.class_name == p.class_name
            and o.confidence >= p.min_conf
            and now - o.last_seen_ms <= p.max_stale_ms
        ]

    if op == "any":
        for p in preds:
            m = match(p)
            if m:
                return m
        return []
    if op == "all":
        out = []
        for p in preds:
            m = match(p)
            if not m:
                return []
            out.extend(m)
        return out
    if op == "none":
        return [] if all(not match(p) for p in preds) else [object()]  # non-empty => present
    raise ValueError(f"unknown op {op}")
