# ARK NEXUS X

An autonomous desktop automation operating system for ARK: Survival Evolved and ARK: Survival Ascended.

> Rust/Tauri + React desktop shell, a Python/OpenCV/YOLO vision sidecar, sandboxed NexusScript automation, AI agents, scheduler, device integration, and a self-improving autopilot.

## Features

- **Macro Engine** — timeline recording, deterministic replay, and latency compensation
- **AI Agent Framework** — behavior-tree agents with LLM planning and vision verification
- **Computer Vision** — DXGI capture, YOLO detection, OCR, and a structured screen-state model
- **NexusScript VM** — a sandboxed bytecode interpreter for programmable workflows
- **Scheduler & Multi-Character** — cron-like jobs, guards, profiles, and character switching
- **Input Engine** — SendInput, hooks, and virtual gamepad (ViGEm) with a kill-switch
- **Decision Engine** — situation assessment, rule costs, LLM planner, and escalation
- **Device Integration** — Logitech, Razer, Corsair, and Stream Deck bindings
- **Self-Improvement Loop** — telemetry, tuning parameters, and governed learning
- **Marketplace & Plugins** — signed packages, capability grants, and a permissioned plugin host

## Architecture

```
+--------------------- FRONTEND (React + TypeScript, Tauri webview) ---------------------+
|  Dashboard | Macro Studio | Agent Panel | Scheduler UI | Marketplace UI                |
+----------------------------------------+-----------------------------------------------+
                                         | Tauri IPC (typed commands + events)
+----------------------------------------v-----------------------------------------------+
| DESKTOP SHELL (Rust, Tauri main process) — AppState | config | lifecycle | logging       |
+------+----------------+----------------+----------------+----------------+-------------+
       |                |                |                |                |
+------v------+  +------v------+  +------v-------+  +----v-------------+
| Input      |  | Macro       |  | Scheduler &  |  | Device           |
| Engine     |  | Engine      |  | Multi-Char   |  | Integration      |
+------+------+  +------+------+  +------+-------+  +----+-------------+
       |                |                |                |
+------v----------------v----------------v----------------v-----------------------+
| AUTOMATION CORE (Rust)                                                          |
|  NexusScript VM | Decision Engine | Agent Framework | Blackboard | Marketplace   |
+------+----------------------------------------------+----------------------------+
       | ZeroMQ IPC                                    | Tauri commands
+------v----------------------------------------------v----------------------------+
| PYTHON SIDECAR (Vision & AI) — capture | OpenCV | YOLO (ONNX/TensorRT) | OCR |    |
|  screen-state model | local LLM (Ollama) | cloud adapters                          |
+-----------------------------------------------------------------------+
       |
+------v------------------------------------------------------------------+
| ARK GAME PROCESS + OS (SendInput, hooks, ViGEm, etc.)                  |
+-----------------------------------------------------------------------+
```

## Repository Layout

```
apps/
  frontend/        # React + TypeScript + Vite UI (12 panels, mock IPC)
crates/
  nexus-input      # input engine
  nexus-macro      # macro engine
  nexus-script     # NexusScript sandboxed VM
  nexus-core       # core automation primitives
  nexus-agents     # behavior-tree agent framework
  nexus-vision     # vision pipeline integration
  nexus-decision   # decision engine
  nexus-scheduler  # scheduler & multi-character
  nexus-market     # marketplace & plugin host
  nexus-selfimprove# self-improvement loop
  nexus-breeding   # breeding / mutation tracking
  nexus-model      # model runtime abstraction
sidecar/
  nexus_vision/    # Python vision & AI sidecar (20 tests)
docs/              # design documentation (00-overview … 14-frontend)
```

## Getting Started

### Prerequisites

- Rust (stable toolchain)
- Node.js ≥ 20 and npm
- Python 3.11+ (vision sidecar)
- Windows 10/11 (input automation targets Windows APIs)

### Build

```bash
# Rust workspace (automation core)
cargo build --release

# Frontend
cd apps/frontend
npm ci
npm run build

# Vision sidecar
cd sidecar
python -m pip install -e .
python -m pytest
```

## Documentation

The full design documentation lives in [`docs/`](docs/README.md):

| Area | Docs |
|------|------|
| System overview | [00-overview](docs/00-overview.md) |
| Input & macros | [01-input-engine](docs/01-input-engine.md), [02-macro-engine](docs/02-macro-engine.md) |
| Scripting & vision | [03-nexusscript](docs/03-nexusscript.md), [04-vision-pipeline](docs/04-vision-pipeline.md) |
| Agents & decision | [05-agent-framework](docs/05-agent-framework.md), [08-decision-engine](docs/08-decision-engine.md) |
| Scheduler & device | [06-scheduler](docs/06-scheduler.md), [12-device-integration](docs/12-device-integration.md) |
| Marketplace & learning | [09-marketplace-plugins](docs/09-marketplace-plugins.md), [10-self-improvement](docs/10-self-improvement.md) |
| Shell & UI | [13-desktop-shell](docs/13-desktop-shell.md), [14-frontend](docs/14-frontend.md) |

## Design Principles

1. **Local-first** — core automation runs on the user's machine; cloud AI is optional and opt-in.
2. **Layered and decoupled** — subsystems communicate over typed message buses, not direct calls.
3. **Deterministic core, stochastic edge** — input and macros are deterministic; LLM decisions are confined to the planner layer.
4. **Safe by construction** — NexusScript runs sandboxed with explicit capability grants; plugins are signed and permissioned.
5. **Observable** — every action is recorded to telemetry for replay, debugging, and self-improvement.

## License

[MIT](LICENSE) © PlayNexus
