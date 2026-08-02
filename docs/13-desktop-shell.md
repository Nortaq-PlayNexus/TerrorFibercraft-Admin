# 13 — Desktop Shell

## Purpose

The Desktop Shell is the Rust/Tauri main process that hosts the entire automation system: window lifecycle, configuration and persistence, IPC between the React frontend and the Rust core, the plugin host, and supervision of sidecar processes (Vision, LLM, Device SDKs).

## Process Layout

```
+-----------------+  Tauri IPC (typed, serialized)  +----------------+
| React Webview   | <------------------------------>| Rust Core      |
+-----------------+                                  |  (this doc)    |
                                                     +-------+--------+
                                                             |
                                             +---------------+---------------+
                                             |               |               |
                                    +--------v----+   +-----v-----+   +-----v------+
                                    | Vision sidecar | | LLM worker| | Device SDKs|
                                    +----------------+ +-----------+ +------------+
```

## Responsibilities

### 1. Application lifecycle
- Single-instance enforcement (a second launch focuses the running window).
- Graceful shutdown: quiesce agents → flush input queue → stop sidecars → save state.
- Auto-restart supervision: if Vision sidecar dies, respawn (bounded retries); keep UI alive with a degraded banner.
- Crash watchdog: worker subprocess heartbeats; unresponsive workers are killed and restarted.

### 2. Configuration & persistence
- **Config store**: user config in `%APPDATA%/ArkNexusX/config.json`; defaults embedded in binary; schema-validated on load.
- **Secrets**: Windows Credential Manager (via `keyring` crate). Never stored in config/DB (cloud keys, marketplace signing keys).
- **SQLite** at `%APPDATA%/ArkNexusX/nexus.db` — telemetry, KB, jobs, macro library, marketplace cache. WAL mode; single writer with timeouts.
- Layered config precedence: defaults < marketplace packages < user < runtime overrides (profile-specific).

### 3. IPC
- Tauri **commands** (Rust ← frontend): typed, permission-checked (each command declares required capability; e.g., `screen:read`, `input:send`).
- Tauri **events** (Rust → frontend): state pushes (`agent.status`, `vision.frame_summary`, `tuning.applied`, telemetry stream).
- **Command throttling**: high-frequency commands (e.g., requesting vision state at 30 Hz) are de-dup'd to a bounded subscription model.
- **Sidecar IPC**: Rust ↔ Python via ZeroMQ (`zeromq` crate + `pyzmq`); protobuf messages in a shared `proto/` crate. Auth token handshake at startup (generated per-launch, bound to process handles).

### 4. Plugin host
- Loads Rust `Plugin` (doc 09) from `%APPDATA%/ArkNexusX/plugins/` with the capability filter applied.
- Plugins run on a dedicated task pool; a panic in a plugin is isolated (thread abort), logged, and the plugin marked crashed.
- Plugin registry: name, version, capabilities, status; queried by the Marketplace UI.

### 5. Logging & diagnostics
- Structured logs (`tracing`) → rolling files + in-app log viewer.
- **Crash dumps**: minidump collection for sidecars.
- **Health endpoint**: in-memory status snapshot (processes, queue depth, model load, device status) exposed to the UI "System" panel and used by the watchdog.

### 6. System integration
- **Startup policy**: launch on login (opt-in), start minimized, delayed auto-connect to the ARK window.
- **Global hotkeys**: registered with the OS (doc 01) for record/kill-switch/toggle.
- **Game detection**: find ARK window by title heuristics (Steam/ASA), report its rect to Vision capture (doc 04).
- **Update mechanism**: Tauri updater for app shell; sidecar Python env bundled per release (venv image, no pip-on-first-run).

## Data Locations

| Path | Content |
|---|---|
| `%APPDATA%/ArkNexusX/config.json` | user config |
| `%APPDATA%/ArkNexusX/nexus.db` | telemetry, KB, jobs, macros, marketplace |
| `%APPDATA%/ArkNexusX/plugins/` | installed plugins/packages |
| `%APPDATA%/ArkNexusX/models/` | downloaded model assets |
| `%LOCALAPPDATA%/ArkNexusX/logs/` | rolling logs + minidumps |
| Credential Manager | cloud API keys, signing keys |

## Security

- All IPC commands run capability checks (no capability-bypass path; enforced at compile time via a macro `#[command(requires = "screen:read")]`).
- Webview uses `capabilities` from Tauri config (only `core:default`, `shell:none` by default).
- Secrets never cross the IPC boundary; only "has_value"/scoped-least view is exposed to the UI.
- Sidecar bind address is loopback-only with a per-launch token; TLS not needed on loopback but token prevents local cross-process callers.

## API Surface (selection)

```rust
// commands exposed to frontend (permission-annotated)
#[command(requires = "config:rw")] fn set_config(key: String, value: Value) -> Result<()>;
#[command(requires = "state:read")] fn snapshot() -> Result<SystemSnapshot>;
#[command(requires = "sidecar:ctrl")] fn restart_vision() -> Result<()>;

// sidecar protocol (proto/manager.proto)
service SidecarManager {
  rpc Hello(HelloReq) returns (HelloAck);   // token handshake + version
  rpc Ping(Empty) returns (Pong);           // heartbeat
  rpc Shutdown(Empty) returns (Empty);
}
```

## Failure Scenarios

| Scenario | Behavior |
|---|---|
| Vision sidecar crash | respawn (≤3), UI banner "Vision degraded", agents wait |
| LLM unavailable | Decision Engine falls back to rules-only (doc 08) |
| Device SDK hang | provider timeout → mark dead → re-init on retry |
| Disk full | telemetry writer trims oldest; warn UI |
| Webview renderer crash | reload webview, keep Rust core state |
