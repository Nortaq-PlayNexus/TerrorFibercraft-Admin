# 02 — Macro Engine

## Purpose

The Macro Engine records raw input timelines, lets users edit them into reusable macros, and replays them deterministically with latency compensation and conditionals.

## Data Model

### Recording
During capture, the Input Engine streams `InputEvent`s (doc 01). The Macro Engine packs them into a timeline:

```rust
struct Macro {
    id: Uuid,
    name: String,
    version: u32,
    timeline: Vec<MacroNode>,
    meta: MacroMeta,           // device, resolution, game, recorded duration
    hash: String,              // content hash for dedup + marketplace signing
}

enum MacroNode {
    Delay { ms: f64 },
    Key { event: InputEvent },           // full fidelity
    Condition { gate: GateExpr, then: Vec<MacroNode>, else: Vec<MacroNode> },
    Call { macro_id: Uuid, args: Vec<Value> },   // composition
    Vision { wait_for: VisionQuery, timeout_ms: u64 },  // integrate with doc 04
    Script { nexus_code: String },                 // inline NexusScript
}
```

### Abstraction levels
1. **Raw timeline**: exact recorded events (debugging, fidelity).
2. **Cleaned timeline**: delays merged/snapped, redundant pairs removed, keys rebindable to the user's current bindings.
3. **Parametric macro**: variable placeholders (`{{attack}}`) bound at run time by agents/scheduler.

## Recording

1. User starts recording → Input Engine hook activates.
2. Events stream into a ring buffer with monotonic timestamps.
3. Dead-time collapsing: gaps < `snap_ms` (default 50ms) are merged; long idle gaps become `Delay` nodes.
4. On stop, the timeline is cleaned, hashed, and stored in the DB.

**Replay fidelity** is measured as *timing error*: `|actual_ts - ideal_ts|` across replays; the engine reports it so users/self-improvement can tune `snap_ms`.

## Replay

### Determinism
- Monotonic clock ticks drive a `replay_cursor`. Each node emits when its timestamp arrives.
- Fixed tick (default 1ms) reduces jitter vs. `sleep()`-based pacing.

### Latency compensation
- Measure round-trip: inject a marker key, detect it via capture hook, compute engine latency.
- `compensated_ts = ideal_ts + measured_latency + safety_margin(5ms)`.
- Adaptive: latency is re-measured on a schedule; spikes trigger `Delay` inflation rather than dropped events.

### Composition
- `Call` nodes allow reusable sub-macros (e.g., `craft_paste` used by many farmers). Nesting depth is capped (default 8) to prevent cycles.
- `Vision` nodes pause the cursor until a `VisionQuery` succeeds or times out (e.g., wait for inventory window to open).

## Editing UI Model (brief)

The Macro Studio (doc 14) renders the timeline as a track editor:
- Drag nodes to change order/timing; edit `Delay` durations numerically.
- Convert a raw segment into a `Condition` via "learn this branch": the engine records input AND screen state during that segment, then the user picks the condition.
- Highlight "clean" vs "raw" so users trust the abstraction.

## API Surface

```rust
impl MacroEngine {
    fn record_start(&self, cfg) -> Result<RecorderId>;
    fn record_stop(&self, id) -> Result<Macro>;
    fn save(&self, m: &Macro) -> Result<Uuid>;
    fn load(&self, id: Uuid) -> Result<Macro>;
    fn clean(&self, m: Macro, opts: CleanOpts) -> Macro;
    fn instantiate(&self, m: &Macro, bindings: &VarMap) -> Result<Macro>;
    fn play(&self, m: &Macro) -> Result<PlayHandle>;         // async
    fn play_one(&self, m: &Macro) -> Result<ReplayReport>;   // blocking w/ report
    fn stop(&self, handle: PlayHandle) -> Result<()>;
    fn latency(&self) -> Duration;
}
```

## ReplayReport (telemetry input)

```rust
struct ReplayReport {
    macro_id: Uuid,
    start: Instant, end: Instant,
    events_sent: u64, events_dropped: u64,
    timing_error_p95_ms: f64,
    vision_waits: Vec<VisionOutcome>,
    abort_reason: Option<AbortReason>,   // kill-switch, user input, timeout
}
```

Reports feed the Self-Improvement loop (doc 10) and the Decision Engine's risk model (doc 08).

## Concurrency Rules

- One macro playback at a time per producer; macros from different producers interleave only via the Input Engine scheduler's priority.
- `Call` depth and total runtime are bounded; loops must have an explicit max-iteration or timeout to satisfy the sandbox's liveness checks.
