# 14 — Frontend

## Purpose

The Frontend is the React + TypeScript UI hosted in the Tauri webview. It is the primary control surface: dashboards, the Macro Studio, agent controls, scheduler, marketplace, KB editor, device settings, and telemetry views. It never talks to the OS directly — all behavior goes through the Rust core's typed commands and events (doc 13).

## Tech Stack

- **React 18 + TypeScript**, Vite build, Tauri webview.
- **State**: Zustand stores (UI state) + a subscription layer over Tauri events (core state). No heavy global query cache; core is source of truth.
- **Styling**: Tailwind (or CSS Modules) — dark theme optimized for long sessions.
- **Charts**: lightweight custom canvas or Recharts for telemetry/history.
- **Code editor** (NexusScript): Monaco or CodeMirror with the tree-sitter NexusScript grammar (doc 03).

## Layout & Panels

```
+------------------------------------------------------------------------------+
| Top bar: mode (Manual/Assisted/Autonomous) | kill-switch | status pills       |
+------------------------------------------------------------------------------+
| Side nav | Main panel (routes)                                                |
|  Dashboard|                                                                   |
|  Macro    |                                                                   |
|  Studio   |                                                                   |
|  Agents   |                                                                   |
|  Schedule |                                                                   |
|  Breeding |                                                                   |
|  Vision   |                                                                   |
|  Scripts  |                                                                   |
|  Devices  |                                                                   |
|  Market   |                                                                   |
|  KB       |                                                                   |
|  Telemetry|                                                                   |
|  Settings |                                                                   |
+----------+--------------------------------------------------------------------+
```

### 1. Dashboard
- Live state: agent cards (state, budget, progress), world snapshot summary (vision), inventory quick-reads, active job queue, recent telemetry sparklines.
- Global mode control + emergency stop (duplicated from hotkey).

### 2. Macro Studio
- Track editor (doc 02): timeline, node cards, delay/condition editing, record/stop/play controls.
- "Record & learn branch" wizard for turning raw segments into conditional macros.
- Replay report panel (timing error, drops, vision waits).

### 3. Agents
- List + spawn agents (Farmer, Breeder, Tamer, ...), per-agent config (goal, budget, grants, params).
- Live BT inspector: hover a running tree node → last tick details (inputs, verification result).
- Lease view: which agent holds input, TTL, contention warnings.

### 4. Scheduler
- Job CRUD with cron editor (human-readable preview), guards, retry policies.
- Calendar/timeline view of upcoming runs; job history table with outcomes.

### 5. Breeding
- Lineage viewer (from KB `my_tames`), mutation tracker (parents → offspring predictions vs observed), imprint/maturation timers, pairing suggestions from Decision Engine.

### 6. Vision
- Live screen preview (blurred/region-masked by default for privacy), overlay of detections, OCR text dump, confidence stats per class, layout-tagging tool for new HUD templates.

### 7. Scripts (NexusScript)
- Editor with syntax/lint (`nexus check` integration), capability inspector, run/debug (breakpoints emit to the VM), telemetry-per-line view.

### 8. Devices
- Provider status (Logitech/Razer/Corsair/Stream Deck), action map table (button → NEXUS command), FX preview (throws a test effect), rebind UI.

### 9. Marketplace
- Browse/search packages, capability & trust badges, install/uninstall/update with diff preview, review-tier filter, publish wizard (packager CLI wrapper).

### 10. KB
- Browse/search encyclopedia; edit user entries (validation on save); import knowledge packs.

### 11. Telemetry
- Charts (macro timing error, agent success, vision confidence), event log viewer with correlation-id drill-down, tuning history (self-improvement applied/rolled back).

### 12. Settings
- Config forms (auto-generated from the config schema), secrets (key presence only; edit routes to Credential Manager), model runtime device selection + benchmarks, mode/policy toggles.

## State & Event Flow

- **Commands** (request/response): `invoke('set_config', {..})`.
- **Events** (push): core pushes typed payloads; the frontend keeps a normalized store and renders.
- **High-frequency** (vision summaries, agent ticks): batched event channel (e.g., 10 Hz max) to avoid webview flooding; charts downsample.
- **Optimistic UI** only for instant-local actions (dismissing a toast); all state-affecting actions await command ack.

## Capabilities & Permissions

- UI renders only what the current capability set allows (e.g., no Marketplace "install" button if `network` is globally disabled).
- Panels hide/disable based on active profile and mode (doc 06, 01).
- All destructive actions (delete macro, uninstall package, kill switch reset) require confirmation; kill-switch itself is instant.

## Accessibility & UX

- Keyboard navigable; high-contrast option; reduced-motion option.
- Long-running actions always show progress with cancel; never a frozen webview.
- Notifications (in-app + optional tray) for alerts: imprint ready, tame complete, agent blocked, tuning applied.

## Webview ↔ Core Contract

- Single typed API surface (`src/api/generated.ts` from the Rust command specs via `tauri-specta` or manual mirror).
- Shared schema package `shared/` (JSON-Schema / zod) so commands and events cannot drift from Rust types.
- No direct DOM/OS access from core; no SQL/fs access from webview.

## Performance

- Virtualized long lists (macro nodes, telemetry, KB search results).
- Canvas rendering for vision overlay, not DOM.
- Event fan-in throttled; webview stays interactive even while agents run at 30 Hz.
