"""Screen-state model shared between the sidecar and the Rust core.

The JSON shape here mirrors crates/nexus-vision screen state so the
ZeroMQ boundary stays versioned and typed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict


@dataclass
class PlayerState:
    hp: float = 1.0
    weight: float = 0.0
    stamina: float = 1.0
    inventory_open: bool = False


@dataclass
class HudState:
    taming_percent: float | None = None
    taming_effectiveness: float | None = None
    maturation_percent: float | None = None
    imprint_percent: float | None = None
    coords: tuple[float, float] | None = None


@dataclass
class DetectedObject:
    track_id: int
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h
    world: tuple[float, float] | None = None
    last_seen_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.track_id,
            "class": self.class_name,
            "conf": self.confidence,
            "bbox": list(self.bbox),
            "world": list(self.world) if self.world else None,
            "last_seen_ms": self.last_seen_ms,
        }


@dataclass
class OcrRegion:
    bbox: tuple[int, int, int, int]
    text: str
    confidence: float
    kind: str  # "item_name" | "taming" | "coords" | ...


@dataclass
class ScreenState:
    schema: int = 3
    captured_at_ms: int = 0
    fps: float = 30.0
    player: PlayerState = field(default_factory=PlayerState)
    hud: HudState = field(default_factory=HudState)
    objects: list[DetectedObject] = field(default_factory=list)
    ocr: list[OcrRegion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 1.0

    def snapshot(self, now_ms: int | None = None) -> dict:
        d = asdict(self)
        d["captured_at_ms"] = now_ms or time.time_ns() // 1_000_000
        d["objects"] = [o.to_dict() for o in self.objects]
        d["ocr"] = [asdict(r) for r in self.ocr]
        if self.hud.coords:
            d["hud"]["coords"] = list(self.hud.coords)
        return d
