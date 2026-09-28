# 12 — Device Integration

## Purpose

Device Integration connects NEXUS to the user's peripheral ecosystem: Logitech (LGHUB/G), Razer (Synapse), Corsair (iCUE), and Stream Deck. Uses: game-specific macros triggered from device buttons, RGB feedback on agent state, Stream Deck key binding to NEXUS commands, and input bridging where a device can act as a virtual keyboard/mouse.

## Architecture

```
+------------------------------------------------------------------+
| DeviceManager (Rust core)                                        |
|  - discovers installed vendor SDKs                                |
|  - central event routing: device events -> NEXUS actions          |
|  - outbound control: NEXUS state -> device effects                |
+---------+-----------+------------+-------------+------------------+
          |           |            |             |
+---------v----+ +----v--------+ +-v-----------+ +-v----------------+
| Logitech    | | Razer       | | Corsair     | | Stream Deck      |
| (LGS SDK /  | | (Synapse /  | | (iCUE SDK / | | (Deck SDK /      |
|  Logi API)  | |  Razer SDK) | |  CUE SDK)   | |  Deck API)       |
+-------------+ +-------------+ +-------------+ +------------------+
```

Each vendor binding is an optional, dynamically-loaded provider behind a common trait:

```rust
pub trait DeviceProvider: Send + Sync {
    fn name(&self) -> &'static str;
    fn detect(&self) -> Result<DeviceInfo, DeviceError>;   // hardware present?
    fn bind(&self, actions: &DeviceActionMap) -> Result<()>;
    fn handle(&self, event: DeviceEvent) -> Result<()>;
    fn set_fx(&self, fx: FxSpec) -> Result<()>;           // RGB etc.
    fn unload(&self);
}
```

## Vendor Bindings (provider responsibilities)

### Logitech
- **LGS/Logi API**: keyboard/mouse/headset RGB (e.g., keyboard pulses blue while an agent farms). Detection via `LogiLedInit()` probe; gracefully no-op if absent.
- **Logitech G HUB**: macro buttons → map to NEXUS commands. If present, prefer its local macro engine to avoid dual handling.

### Razer
- **Synapse 3/4 Chroma SDK**: `RzChromaInit` → device effect sets. Map agent state to lighting zones (idle/working/danger).
- **Razer devices (keyboard/mouse)**: optional key remap pass-through so NEXUS can emit virtual keys via Razer's virtual device (only when user enables).

### Corsair
- **iCUE SDK (CUESDK)**: `CorsairPerformProtocolHandshake` → set color on strips/keys/effects. Detection and unload handling required (SDK is process-global on some versions).

### Stream Deck
- **Elgato Stream Deck SDK (WS)**: JSON over WebSocket; provides buttons, sends `keyUp`/`keyDown` events, receives icon updates.
- Buttons bound to NEXUS: `run_macro`, `toggle_agent`, `kill_switch`, `record`, `status_icon`.
- Icons dynamically updated from NEXUS state (agent running → running icon).

## Event Model

- **Inbound** (device → NEXUS): buttons/keys pressed become `DeviceEvent { source, event, payload }`. These are validated against the action map and turned into NEXUS commands through the same arbitration as hotkeys (doc 01) — the kill-switch is always bound first.
- **Outbound** (NEXUS → device): state changes (agent status, taming %, low inventory) become `FxSpec` (RGB) or `IconSpec` (Stream Deck). Bounded rate (e.g., ≤2 fx updates/sec to avoid flicker).

## Action Map

```json
{
  "logitech": { "mouse.g7": { "type": "run_macro", "ref": "farm-metal", "rate_limit_s": 5 } },
  "streamdeck": {
    "key:0,0": { "type": "toggle_agent", "ref": "farmer" },
    "key:0,1": { "type": "kill_switch" }
  },
  "razer": { "fx": { "agent.farmer": "pulse_blue", "agent.tamer": "pulse_amber", "danger": "red" } },
  "corsair": { "fx": { "taming>75%": "stripe_green", "low_health": "blink_red" } }
}
```

## Safety & Robustness

- **Optional everywhere**: no vendor SDK required; all providers auto-detect and silently unload on failure. NEXUS runs 100% without them.
- **Rate limits** on outbound effects; no device SDK call may block the automation core (each provider runs on its own task, calls wrapped in timeouts).
- **SDK lifecycle**: re-init on vendor app restart (LGHUB/iCUE commonly restart); provider emits `resync` event.
- **Permission**: device actions are part of the capability `device` (docs 03/09). Installing a package that maps device buttons requires user confirmation showing the exact bindings.
- **No interception of secure input**: device bindings never read/forward passwords or typed secrets.

## Configuration

- `devices.enabled.<vendor>`, `devices.action_map`, `devices.fx_map`, `devices.poll_ms`.
- Stored in config (doc 13), editable in the Devices settings panel (doc 14).

## API Surface

```rust
impl DeviceManager {
    fn providers(&self) -> Vec<ProviderStatus>;
    fn set_action_map(&self, map: DeviceActionMap) -> Result<()>;
    fn fire(&self, spec: FxSpec) -> Result<()>;          // outbound effects
    fn rebind(&self, device: DeviceId, button: ButtonId, action: DeviceAction) -> Result<()>;
    fn on_event(&self, cb: impl Fn(DeviceEvent) + Send + 'static);  // inbound
}
```
