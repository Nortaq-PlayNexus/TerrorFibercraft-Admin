# 04 — Vision Pipeline

## Purpose

The Vision Pipeline converts raw screen frames into a structured, queryable **Screen State Model**. It is the sensory subsystem: everything that needs to "see" ARK — agents, NexusScript's `vision.*`, macro `Vision` nodes, and the Decision Engine — reads from this model. It runs in the Python sidecar for GPU-friendly frame processing.

## Pipeline Stages

```
DXGI Desktop Duplication (capture)
        |  BGRA frame @ native res (capped fps)
        v
Frame Preprocess (OpenCV)
   - downscale, color normalize (ARK HUD palette), denoise
        |
        +------------------------------+----------------------------+
        v                              v                            v
   YOLO Detector                OCR Pipeline                 HUD/Pixel Parsers
   (objects: dinos,             (inventory counts,           (health bars, weight
    nodes, structures,           item names, chat,            %, taming %, coords)
    players)                     taming % text)
        |                              |                            |
        +---------------+--------------+----------------------------+
                        v
            Temporal Fusion (tracking)
        - detections matched across frames (IoU + appearance)
        - velocity/position estimation, remove flicker
                        |
                        v
              Screen State Model  (JSON, versioned)
                        |
                        +-----------> ZeroMQ PUB  ->  Rust (agents, VM, engine)
                        +-----------> SQLite cache ->  history for telemetry
```

## Sub-Stages Detail

### 1. Capture (DXGI Desktop Duplication)
- Dedicated thread, owns the GPU adapter, captures only the display region containing ARK (auto-detected from window rect, or explicit monitor select).
- Configurable **cap fps** (default 30; 15 for scripts that don't need fast vision; 60 for taming/imprint timing).
- Drops frames under load rather than backlogging.

### 2. Preprocess
- Downscale to detector input (e.g., 640px) with aspect-preserving letterbox.
- Optional **ARK palette filter**: reduces reliance on lighting conditions for HUD elements.
- ROI caching: static HUD regions (minimap, hotbar) get their own stable regions to keep OCR fast.

### 3. YOLO Detection
- **Model**: YOLOv8/v11 → exported to ONNX → optionally TensorRT for GPU. See doc 11 for runtime details.
- **Classes (custom ARK dataset)**: `player`, `tamed_dino`, `wild_dino` (per-class for popular tames: rex, giga, argy, anky, doedic, theri, ...), `resource_node` (metal, obsidian, crystal, wood, thatch, stone, berries), `structure`, `item_pickup`, `loot_crate`, `enemy_dino`.
- **Output**: `[class, confidence, bbox, id]`. NMS per class; small-object tuned for distant dinos.
- Training data pipeline: capture→annotate→distill→evaluate; model registry in doc 11.
- Failure handling: on zero detection in a "busy" region for >N seconds, the pipeline emits a `low_confidence` signal so agents fall back to scripted behaviors.

### 4. OCR (PaddleOCR preferred, Tesseract fallback)
- Regions of interest first (HUD, inventory panels) to bound cost.
- **Inventory**: item name + count from grid cells; scroll tracking to know current page.
- **Taming**: `Taming %` number, effectiveness, food value — critical for taming assist.
- **Breeding**: maturation %, imprint %, timer reads.
- Output: structured `TextRegion { bbox, text, confidence, kind }`.

### 5. HUD/Pixel Parsers
- Health bars: row-wise color scan → fraction 0..1.
- Weight/encumbrance: bar fraction + OCR number.
- Coordinates: OCR the HUD coordinate line; enables `navigate_to(x,y)`.
- Hotbar/cooldown: cooldown swipe detection via template matching.
- These are cheap and run every frame; heavy models run at reduced rate.

### 6. Temporal Fusion (Tracker)
- Detection-to-track association via IoU + feature embedding; maintain per-track position, age, last-confirmed.
- Produces stable IDs so agents can say "that rex" rather than "the rex at (x,y) this frame".
- **State staleness**: every track carries `last_seen_ts`; agents/decision engine must account for it (a 5-second-old dino position is a guess).

## Screen State Model (contract)

```json
{
  "schema": 3,
  "captured_at": 1714000000000,
  "fps": 30,
  "game": { "map": "TheIsland", "coords": [80.2, 34.1], "tick": 1234 },
  "player": { "hp": 0.87, "weight": 0.62, "inventory_open": true, "stamina": 0.5 },
  "objects": [
    { "id": "trk-7", "class": "metal_node", "conf": 0.94,
      "bbox": [12, 34, 45, 67], "world": [82.1, 30.5], "last_seen_ms": 120 }
  ],
  "hud": {
    "taming": { "active": true, "percent": 0.43, "effectiveness": 1.0 },
    "maturation": { "percent": 0.1, "imprint": 0.0 },
    "cooldowns": { "pick": 0.2, "weapon": 0.8 }
  },
  "ocr": [ { "bbox": [...], "text": "Metal Ingot", "conf": 0.99, "kind": "item_name" } ],
  "confidence": 0.91,
  "warnings": [ "low_confidence_objects", "tracking_stale" ]
}
```

## API

Rust side exposes a **VisionClient** over ZeroMQ:

```rust
impl VisionClient {
    fn state(&self) -> Result<ScreenState>;
    fn wait_for(&self, query: VisionQuery, timeout: Duration) -> Result<ScreenState>;
    fn query(&self, q: VisionQuery) -> Result<QueryResult>;
}
```

`VisionQuery` example: `{ "op": "any", "and": [ {"class":"metal_node"}, {"class":"anky","near":"player","dist":20.0} ] }`.

Python side exposes:
```python
class VisionPipeline:
    def ingest(frame: np.ndarray) -> None
    def snapshot() -> ScreenState
    def subscribe(consumer: Callable[[ScreenState], None])
```

## Performance Budget

| Stage | Target |
|---|---|
| Capture | native FPS, zero-copy |
| Preprocess | <2 ms @640p |
| YOLO (ONNX/CPU) | <25 ms/frame |
| YOLO (TensorRT/GPU) | <8 ms/frame |
| OCR (ROI) | <10 ms/region |
| HUD parsers | <1 ms |
| End-to-end staleness | <60 ms typical |

## Failure & Degradation

- **GPU driver reset**: re-init adapter, notify UI, agents pause vision-dependent steps.
- **Ark minimized**: capture yields `NoFrame`; agents wait (do not spam inputs to a backgrounded window).
- **Unknown UI layout** (new update, different mod): `warnings` mark it; Decision Engine may ask user to point-and-tag the layout (which becomes a layout template stored in the Knowledge DB).
