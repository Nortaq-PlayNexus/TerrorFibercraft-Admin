# ARK NEXUS X — System Overview

## Purpose

ARK NEXUS X is a desktop automation operating system for ARK: Survival Evolved / ARK: Survival Ascended. It unifies macro recording, AI agents, computer vision (YOLO + OCR), input automation, device integration (Logitech/Razer/Corsair/Stream Deck), scripting (NexusScript), breeding/taming assistants, and a self-improving autopilot into one extensible platform.

## Design Principles

1. **Local-first** — all core automation runs on the user's machine; cloud AI is optional and opt-in.
2. **Layered and decoupled** — each subsystem communicates over typed message buses, not direct calls.
3. **Deterministic core, stochastic edge** — input and macros are deterministic; LLM decisions are confined to the planner layer.
4. **Safe by construction** — NexusScript runs in a sandbox with explicit capability grants; plugins are signed and permissioned.
5. **Observable** — every action is recorded to a telemetry log for replay, debugging, and self-improvement.

## System Diagram

```
+--------------------------------------------------------------------------+
| FRONTEND (React + TypeScript, Tauri webview)                              |
|  Dashboard | Macro Studio | Agent Panel | Scheduler UI | Marketplace UI   |
+-------------------------------|-------------------------------------------+
                                 | Tauri IPC (typed commands + events)
+-------------------------------v-------------------------------------------+
| DESKTOP SHELL (Rust, Tauri main process)                                  |
|  AppState | Window manager | Lifecycle | Logging | Config (SQLite + JSON) |
+------+----------------+----------------+----------------+-----------------+
       |                |                |                |
+------v------+  +------v------+  +------v-------+  +----v-------------+
| Input      |  | Macro       |  | Scheduler &  |  | Device           |
| Engine     |  | Engine      |  | Multi-Char   |  | Integration      |
|            |  |             |  |              |  | (RGB/macros/hw)  |
+------+------+  +------+------+  +------+-------+  +----+-------------+
       |                |                |                |
+------v----------------v----------------v----------------v------+
| AUTOMATION CORE (Rust)                                          |
|  NexusScript VM | Decision Engine | Agent Framework (Behavior) |
|  Blackboard | Marketplace | Self-Improvement Loop              |
+------+----------------------------------------------+----------+
       | ZeroMQ IPC                                      | Tauri commands
+------v----------------------------------------------+----------+
| PYTHON SIDECAR (Vision & AI)                                     |
|  Capture (DXGI) | OpenCV preprocess | YOLO (ONNX/TensorRT)      |
|  OCR | Screen-State Model | Local LLM (Ollama) | Cloud adapters  |
+-----------------------------------------------------------------+
       |
+------v------------------------------------------------------------------+
| ARK GAME PROCESS (steam/other) + OS (SendInput, hooks, ViGEm, etc.)     |
+-----------------------------------------------------------------------+
```

## Subsystems

| # | Doc | Responsibility |
|---|-----|----------------|
| 01 | Input Engine | Sending and capturing keyboard/mouse/controller input via Windows APIs |
| 02 | Macro Engine | Recording, editing, and replaying timelines with latency compensation |
| 03 | NexusScript VM | Sandboxed bytecode interpreter for programmable workflows |
| 04 | Vision Pipeline | Frame capture, YOLO detection, OCR, and a structured screen-state model |
| 05 | Agent Framework | Behavior-tree agents with LLM planning and vision verification |
| 06 | Scheduler & Multi-Char | Cron-like jobs, per-profile configurations, character switching |
| 07 | Knowledge DB | ARK encyclopedic data (tames, mats, recipes, breeding tables) |
| 08 | Decision Engine | Rules + cost model selecting goals; LLM fallback for ambiguity |
| 09 | Marketplace & Plugins | Signed package install, versioning, permissions, community sharing |
| 10 | Self-Improvement | Telemetry-driven reward signals and script/macro parameter tuning |
| 11 | Model Runtime | Local and cloud model management, inference abstraction |
| 12 | Device Integration | Logitech/Razer/Corsair/Stream Deck bindings |
| 13 | Desktop Shell | Tauri lifecycle, config storage, IPC, plugin host |
| 14 | Frontend | React UI panels and their responsibilities |

## Cross-Cutting Concerns

- **Typed message buses**: All inter-subsystem communication uses typed payloads (serde/JSON over IPC, protobuf over ZeroMQ). This keeps the Python/Rust boundary versionable and debuggable.
- **Telemetry**: Every input event, vision frame decision, and agent action is an append-only log record with a correlation ID. Enables replay and self-improvement (doc 10).
- **Permission model**: Capabilities (input, screen capture, network, file) are declared and enforced at every boundary: script sandbox, plugin manifest, and device bindings.
- **Configuration**: Three layers — defaults (shipped JSON schema), user overrides (JSON), and secrets (Windows Credential Manager, never in repo).

## Runtime Topology

- **Process A — Main (Rust/Tauri)**: UI, state, macro/input/agent/scheduler cores.
- **Process B — Vision sidecar (Python)**: capture + inference; spawns model workers.
- **Optional Process C — LLM sidecar**: Ollama/llama.cpp local server or remote API client.
- **Optional Process D — Device daemons**: SDK proxies for vendor integration.

Processes A and B exchange frames and state over ZeroMQ; A talks to the webview over Tauri IPC. Crash isolation: if B dies, A keeps the UI alive and shows degraded vision status.

## Operational Modes

1. **Manual** — user drives the game; NEXUS only assists (hotkeys, overlays).
2. **Assisted** — NEXUS suggests or completes single actions (tame assist, imprint remind).
3. **Autonomous** — an enabled agent takes control of the input engine for a bounded goal (e.g., "farm 5k metal").
4. **Scheduled** — scheduler launches agents at configured times (e.g., imprint timers).

Mode is a global state machine; an emergency kill-switch (hotkey + UI button) drops to Manual and flushes queued inputs.
