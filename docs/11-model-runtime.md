# 11 — Model Runtime

## Purpose

The Model Runtime is the single abstraction over all machine-learning models NEXUS uses: vision (YOLO, OCR), planning (LLM), and any future embedding/classification models. It manages local vs. cloud execution, device selection (CPU/GPU), model versioning, and fallbacks.

## Model Categories

| Category | Use | Typical models | Runtime |
|---|---|---|---|
| Object detection | dinos, nodes, structures | YOLOv8/v11 custom | ONNX / TensorRT |
| OCR | inventory, HUD, taming % | PaddleOCR / Tesseract | native CPU/GPU |
| Layout/template match | HUD element location | template matching | OpenCV |
| Planner LLM | goal→plan, natural language | Llama/Phi/Qwen (local), GPT/Claude (cloud) | Ollama/llama.cpp or API |
| Vision-language | describe screen (debug, advanced agents) | Llava/Qwen-VL (optional) | Ollama |
| Embeddings (optional) | KB search, similarity | bge/sentence-transformers | ONNX |

## Architecture

```
+---------------------------------------------------------------+
| ModelRegistry (Rust side)                                      |
|  - declares models, versions, providers, device preference     |
|  - exposes typed client APIs to the rest of the app            |
+----------------------+------------------------+----------------+
                       |                        |
        +--------------v----------+   +---------v--------------+
        | Vision Model Worker     |   |  LLM Worker            |
        | (Python sidecar)        |   |  (local Ollama / API)  |
        |  YOLO .onnx/.engine     |   |                        |
        |  OCR engines            |   |  session prompt mgmt   |
        +-------------------------+   +------------------------+
```

### Registry entry
```json
{
  "id": "yolo-ark-v3",
  "kind": "detector",
  "format": "onnx",                 // or "tensorrt" | "tflite"
  "providers": ["cuda", "tensorrt", "dml", "cpu"],
  "input": { "size": 640, "channels": 3, "normalize": "yolo" },
  "classes": ["player", "tamed_dino", ...],
  "preferred_device": "gpu",
  "min_cuda": "12.0",
  "source": "official-pack://yolo-ark-v3",
  "hash": "sha256:..."
}
```

## Execution Strategy

- **Provider fallback chain**: try CUDA/TensorRT → DirectML → CPU, measured at load with a micro-benchmark (inference of one frame + OCR warm region).
- **Model worker process**: inference runs in the Python sidecar worker (doc 04) so a model crash does not take down the app.
- **Batching**: vision frames coalesced when multiple consumers (agents, script, UI) request — single inference shared.
- **Warmup + persistence**: models stay resident; reload only on version change. Memory pressure → unload least-used.

## Local LLM

- **Server**: Ollama (simplest) or llama.cpp server; spawned/managed by the app or user-run.
- **Selection heuristic** for planning model:
  - RAM/VRAM probe → pick quantized model fitting budget (e.g., `qwen2.5:7b-q4` on 8GB).
  - Latency budget: planning is not frame-critical; allow up to 5–15s.
- **Prompt safety**: planning prompts are built by the Decision Engine (08), templated, and do **not** include secrets. Cloud mode redacts local paths and never sends telemetry.

## Cloud AI Support

- **Adapters**: OpenAI-compatible chat API, Anthropic, custom endpoints (user-configured base URL + key via Windows Credential Manager, doc 13).
- **Policy**:
  - Cloud is opt-in; default local.
  - Data classification: only plan *requests* (situation vector, not raw frames) may go to cloud unless user enables vision-cloud.
  - Rate limits + cost caps per month; user is warned on threshold.
  - Every cloud call logged (non-secret).
- **Failover**: local first; if local unavailable and cloud enabled, transparent fallback with a UI badge.

## Model Management

- **Sources**: official pack (bundled/signed), marketplace models (doc 09), local imports (`.onnx`, `.engine`).
- **Versioning**: registry stores multiple versions; rollback supported.
- **Update flow**: `nexusx model update` downloads hash-verified assets; Vision Pipeline hot-swaps after quiescing the worker.

## Performance & Budgets

- Inference timeouts per model kind; long-running LLM calls are cancelable.
- GPU memory guard: before loading a model, check free VRAM; refuse if it would exceed budget (prevents ARK + model OOM).
- Telemetry: per-model latency, throughput, load count, fallback events → feeds Vision tuning (doc 10).

## API Surface

Rust:
```rust
impl ModelRegistry {
    fn resolve(&self, id: &ModelId) -> Result<ModelHandle>;
    fn list(&self) -> Vec<ModelInfo>;
    fn install_local(&self, path: PathBuf) -> Result<ModelInfo>;
    fn set_device(&self, id: &ModelId, dev: Device) -> Result<()>;
    fn evict(&self, id: &ModelId) -> Result<()>;  // free memory
}
```

Python (worker side):
```python
class DetectorWorker:
    def load(self, model_id: str, provider: str) -> None
    def infer(self, frame: np.ndarray) -> Detections
class OcrWorker:
    def read(self, region: np.ndarray, kind: str) -> TextResult
```
