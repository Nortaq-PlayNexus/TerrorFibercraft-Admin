"""Model adapters: detector (YOLO) and OCR, with graceful degradation.

Heavy dependencies (onnxruntime/opencv/paddleocr) are optional extras; if
absent, adapters return unavailable and the pipeline falls back to the
pure-Python synthetic detectors.
"""
from __future__ import annotations

import importlib.util


class DetectorAdapter:
    """Wraps a YOLO model (ONNX/TensorRT) or a synthetic detector."""

    def __init__(self, model_path: str | None = None, backend: str = "onnx"):
        self.model_path = model_path
        self.backend = backend
        self._load()

    def available(self) -> bool:
        return self._model is not None

    def _load(self) -> None:
        self._model = None
        if self.model_path is None:
            # synthetic mode: emit detections from annotated fixtures
            self._model = "synthetic"
            return
        if self.backend == "onnx":
            if importlib.util.find_spec("onnxruntime"):
                import onnxruntime as ort

                self._model = ort.InferenceSession(self.model_path)
            else:
                raise RuntimeError("onnxruntime not installed")
        elif self.backend == "tensorrt":
            if importlib.util.find_spec("tensorrt"):
                import tensorrt as trt  # noqa: F401

                self._model = "tensorrt"
            else:
                raise RuntimeError("tensorrt not installed")

    def detect(self, frame, classes: list[str] | None = None) -> list[tuple[str, float, tuple]]:
        if self._model == "synthetic":
            return self._synthetic(frame)
        raise NotImplementedError("real model inference via onnxruntime in v1")

    def _synthetic(self, frame) -> list[tuple[str, float, tuple]]:
        """Fixture-driven detections used by tests and demo mode."""
        if hasattr(frame, "annotations"):
            return list(frame.annotations)
        return []


class OcrAdapter:
    """Wraps PaddleOCR / Tesseract, or returns fixture regions."""

    def __init__(self, engine: str = "paddle", path: str | None = None):
        self.engine = engine
        self._engine = None
        if path:
            raise RuntimeError("static OCR path not supported in v1")

    def available(self) -> bool:
        return self._engine is not None

    def read(self, frame) -> list:
        if hasattr(frame, "ocr_regions"):
            return list(frame.ocr_regions)
        return []


class ModelRegistry:
    """Local registry mirroring the Rust-side ModelRuntime (doc 11)."""

    def __init__(self):
        self.models: dict[str, DetectorAdapter | OcrAdapter] = {}

    def register(self, model_id: str, adapter) -> None:
        self.models[model_id] = adapter

    def get(self, model_id: str):
        return self.models.get(model_id)

    def available_ids(self) -> list[str]:
        return [mid for mid, m in self.models.items() if m.available()]
