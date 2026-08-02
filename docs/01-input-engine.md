# 01 — Input Engine

## Purpose

The Input Engine is the single, permissioned gateway for all physical and virtual input into the ARK game process. It provides:

- **Output**: injecting keyboard, mouse, and controller input.
- **Capture**: hooking physical input for macro recording and hotkey handling.
- **Queueing**: ordering, delaying, and prioritizing input from multiple producers (macros, agents, scripts, user).

All producers **must** go through this engine; nothing else may touch the OS input APIs. This guarantees arbitration and auditability.

## Architecture

```
+---------------------+   +----------------------+   +---------------------+
| Macro Engine        |   | NexusScript VM       |   | Agent Framework     |
| (timeline replay)   |   | (scripted actions)   |   | (behavior actions)  |
+----------+----------+   +----------+-----------+   +----------+----------+
           |                         |                          |
           +------------+------------+--------------------------+
                        v
                +--------------+
                |  Scheduler   |  (token buckets, priority, arbitration)
                +--------------+
                        |
                        v
              +-------------------+
              | Input Dispatcher  |  -> telemetry log (every event)
              +-------------------+
                        |
        +---------------+---------------+
        |               |               |
+-------v-------+  +----v----+  +------v---------+
| Keyboard API  |  | Mouse   |  | Controller API |
| (SendInput,   |  | API     |  | (ViGEm/ScpVbus)|
|  low-level)   |  |         |  |                |
+---------------+  +---------+  +----------------+
        |               |               |
        +-------+-------+-------+-------+
                        v
              +--------------------+
              | Windows HID layer  |
              +--------------------+
```

## Output Backends

### Keyboard
- **`SendInput` (primary)**: async, injected, works with most games. Supports unicode + scancodes.
- **Low-level `keybd_event` fallback**: when a game ignores injected flags, retry with `LLKHF_INJECTED` cleared via a proxy keyboard layout.
- **Scan-code fidelity**: prefer hardware scancodes over VK codes so ARK (Unreal) responds correctly to hold/release and rebindable keys.

### Mouse
- **`SendInput` absolute/relative motion** with configurable sensitivity curve.
- **DX mouse (DirectInput) emulation**: `SendInput` also delivers to DirectInput, but some titles filter by device type; optional raw `dxinput` shim.
- **Custom sensitivity curve**: `input_sensitivity = f(raw_delta, game_sensitivity, dpi)`, tuned per user profile.

### Controller
- **ViGEmBus (virtual bus)** or **ScpVbus**: presents a virtual Xbox 360 / DualShock 4 controller. XInput receives the virtual device, so ARK sees a real controller.
- **Mapping**: logical axis/button → physical frame updates (16ms at 60Hz) via a `ControllerFrame` struct.

## Capture

- **Windows hook (WH_KEYBOARD_LL / WH_MOUSE_LL)**: global low-level hooks for hotkeys and macro recording.
- **Raw input (RAWINPUT)**: precise for high-frequency devices; used when LL hooks are too slow or eaten by games.
- **Capture modes**: only active during explicit recording; otherwise the engine records nothing (privacy).
- **Event schema**:
  ```rust
  InputEvent {
      id: u64,
      ts: Duration,          // relative, monotonic
      kind: KeyDown|KeyUp|MouseMove|MouseDown|MouseUp|MouseWheel|Axis|Button|Touch,
      device: Physical|Virtual,
      detail: Keycode | Point | AxisState,
      producer: ProducerId,  // "macro:123", "agent:farmer", "user"
  }
  ```

## Scheduling & Arbitration

- **Token bucket per producer**: limits max event rate to prevent macro storms.
- **Priority order** (high wins):
  1. User (kill-switch, hotkeys)
  2. Agent emergency actions (e.g., disengage)
  3. Scheduler jobs
  4. Macros / scripts
- **Preemption**: when a user input arrives during an agent sequence, the current action is paused after the current atomic step, and control returns to the user.
- **Kill-switch**: a hardware-invariant hotkey (configurable, defaults to `Ctrl+Alt+K`) flushes the queue and drops to Manual mode. The kill-switch is processed in the capture hook directly, never through the queue.

## API Surface

```rust
pub struct InputEngine { /* queue, backends, hooks */ }

impl InputEngine {
    fn send(&self, events: &[InputEvent]) -> Result<(), InputError>;
    fn record_start(&self, capture: CaptureConfig) -> Result<RecorderId, InputError>;
    fn record_stop(&self, id: RecorderId) -> Result<Vec<InputEvent>, InputError>;
    fn register_hotkey(&self, combo: Hotkey, cb: Callback) -> Result<(), InputError>;
    fn set_profile(&self, profile: InputProfile);   // sensitivity, deadzones
    fn queue_status(&self) -> QueueStatus;
}
```

## Configuration (InputProfile)

```json
{
  "mouse": { "sensitivity": 1.0, "accel": false, "curve": "linear", "dpi": 800 },
  "keyboard": { "use_scancodes": true, "key_delay_ms": 8 },
  "controller": { "deadzone": 0.12, "report_rate_hz": 60 },
  "scheduler": { "tokens_per_sec": 300, "burst": 60, "user_priority": true },
  "kill_switch": { "enabled": true, "combo": ["Ctrl", "Alt", "K"] }
}
```

## Safety & Compliance

- Only active while the ARK process is foreground (configurable).
- Every injected event is appended to the telemetry log with producer id (required by Self-Improvement, doc 10).
- No keystroke logging outside explicit recording sessions; recording UI is always visible.
