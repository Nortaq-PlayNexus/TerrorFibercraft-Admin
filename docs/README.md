# ARK NEXUS X — Design Documentation

Autonomous ARK automation operating system. Rust/Tauri + React/TypeScript desktop shell with a Python/OpenCV/YOLO vision sidecar, sandboxed NexusScript automation, AI agents, scheduler, device integration, and a self-improving autopilot.

## Documents

| Doc | Subsystem | Summary |
|-----|-----------|---------|
| [00-overview](00-overview.md) | System overview | Architecture, principles, runtime topology, operational modes |
| [01-input-engine](01-input-engine.md) | Input Engine | SendInput/hooks/ViGEm, capture, scheduling & arbitration, kill-switch |
| [02-macro-engine](02-macro-engine.md) | Macro Engine | Timeline recording, deterministic replay, latency compensation |
| [03-nexusscript](03-nexusscript.md) | NexusScript VM | Language, sandboxed bytecode VM, capabilities, tooling |
| [04-vision-pipeline](04-vision-pipeline.md) | Vision Pipeline | DXGI capture, YOLO detection, OCR, temporal fusion, screen-state model |
| [05-agent-framework](05-agent-framework.md) | Agent Framework | Behavior trees, blackboard, OODA loop, planner, verifiers, agent catalog |
| [06-scheduler](06-scheduler.md) | Scheduler & Multi-Char | Cron/event triggers, guards, profiles, character switching |
| [07-knowledge-db](07-knowledge-db.md) | Knowledge DB | Encyclopedia, breeding/mutation tables, world data, schema, queries |
| [08-decision-engine](08-decision-engine.md) | Decision Engine | Situation assessment, rules, cost model, LLM planner, escalation |
| [09-marketplace-plugins](09-marketplace-plugins.md) | Marketplace & Plugins | Package model, capabilities, signing/trust tiers, plugin host |
| [10-self-improvement](10-self-improvement.md) | Self-Improvement | Telemetry, tuning parameters, learning loop, governance |
| [11-model-runtime](11-model-runtime.md) | Model Runtime | YOLO/OCR/LLM abstraction, local vs cloud, provider fallback, model mgmt |
| [12-device-integration](12-device-integration.md) | Device Integration | Logitech/Razer/Corsair/Stream Deck bindings, event model, safety |
| [13-desktop-shell](13-desktop-shell.md) | Desktop Shell | Tauri lifecycle, config/persistence, IPC, plugin host, sidecar supervision |
| [14-frontend](14-frontend.md) | Frontend | React panels, state/event flow, capabilities, performance |

## Recommended Reading Order

For onboarding: **00 → 13 → 14 → 01 → 04** (system, shell, UI, then the two core engines), then the rest as needed.

## Suggested Monorepo Layout

```
ArkNexusX/
├─ apps/
│  ├─ desktop/        # Tauri app (Rust core + webview)
│  └─ sidecar/        # Python vision & AI sidecar
├─ packages/
│  ├─ core/           # Rust automation core crates
│  ├─ proto/          # protobuf shared schemas
│  ├─ shared/         # shared TS/Rust type schemas
│  └─ nexus/          # NexusScript compiler + VM crate
├─ docs/              # this documentation
└─ assets/
   ├─ kb/             # bundled knowledge seed data
   └─ models/         # model packs (signed)
```
