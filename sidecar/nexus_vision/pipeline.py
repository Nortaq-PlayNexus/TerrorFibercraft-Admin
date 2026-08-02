"""Temporal fusion tracker + screen-state pipeline.

The pipeline ingests frames plus raw detections/OCR from adapters and
produces a ScreenState with stable track ids.
"""
from __future__ import annotations

from .model import DetectedObject, HudState, OcrRegion, PlayerState, ScreenState


class TemporalTracker:
    """Matches detections to tracks by IoU, keeping stable track ids."""

    def __init__(self, iou_threshold: float = 0.3, max_age_ms: int = 5000):
        self.iou_threshold = iou_threshold
        self.max_age_ms = max_age_ms
        self.tracks: list[DetectedObject] = []
        self._next_id = 1

    @staticmethod
    def iou(a: tuple, b: tuple) -> float:
        x1, y1, aw, ah = a
        x2, y2, bw, bh = b
        inter_w = max(0, min(x1 + aw, x2 + bw) - max(x1, x2))
        inter_h = max(0, min(y1 + ah, y2 + bh) - max(y1, y2))
        inter = inter_w * inter_h
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0.0

    def update(self, detections: list[tuple[str, float, tuple]], now_ms: int) -> None:
        self.tracks = [
            t for t in self.tracks if now_ms - t.last_seen_ms <= self.max_age_ms
        ]
        for class_name, conf, bbox in detections:
            best_idx = None
            best_iou = 0.0
            for i, t in enumerate(self.tracks):
                if t.class_name != class_name:
                    continue
                iou = self.iou(t.bbox, bbox)
                if iou >= self.iou_threshold and iou > best_iou:
                    best_idx, best_iou = i, iou
            if best_idx is not None:
                t = self.tracks[best_idx]
                t.bbox = bbox
                t.confidence = conf
                t.last_seen_ms = now_ms
            else:
                self.tracks.append(
                    DetectedObject(
                        track_id=self._next_id,
                        class_name=class_name,
                        confidence=conf,
                        bbox=bbox,
                        last_seen_ms=now_ms,
                    )
                )
                self._next_id += 1

    def fresh(self, class_name: str, now_ms: int, max_stale: int = 2000) -> list[DetectedObject]:
        return [
            t for t in self.tracks
            if t.class_name == class_name and now_ms - t.last_seen_ms <= max_stale
        ]

    def snapshot(self) -> list[DetectedObject]:
        return list(self.tracks)


class VisionPipeline:
    """Owns capture loop state, tracker, and adapter outputs."""

    def __init__(self, fps_cap: float = 30.0, iou_threshold: float = 0.3):
        self.fps_cap = fps_cap
        self.tracker = TemporalTracker(iou_threshold=iou_threshold)
        self.detector = None  # DetectorAdapter (YOLO) when available
        self.ocr_engine = None  # OcrAdapter when available
        self.player = PlayerState()
        self.hud = HudState()
        self.ocr: list[OcrRegion] = []
        self.warnings: list[str] = []
        self.frame_count = 0

    def ingest_frame(self, frame, detections: list[tuple[str, float, tuple]], now_ms: int) -> ScreenState:
        self.frame_count += 1
        self.tracker.update(detections, now_ms)
        if self.frame_count % 10 == 0:
            self.ocr = self._run_ocr(frame, now_ms) if self.ocr_engine else []
        stale = len(self.tracker.tracks) - len(self.tracker.fresh("__any__", now_ms, 60000))
        if stale > 20:
            self.warnings.append("tracking_stale")
        return self._build_state(now_ms)

    def _run_ocr(self, frame, now_ms: int) -> list[OcrRegion]:
        try:
            return self.ocr_engine.read(frame)
        except Exception as exc:  # pragma: no cover - adapter layer
            self.warnings.append(f"ocr_error:{exc}")
            return []

    def _build_state(self, now_ms: int) -> ScreenState:
        return ScreenState(
            captured_at_ms=now_ms,
            fps=self.fps_cap,
            player=self.player,
            hud=self.hud,
            objects=self.tracker.snapshot(),
            ocr=self.ocr,
            warnings=self.warnings,
        )
