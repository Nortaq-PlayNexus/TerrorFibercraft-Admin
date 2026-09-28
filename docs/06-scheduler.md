# 06 — Scheduler & Multi-Character Management

## Purpose

The Scheduler orchestrates time-driven automation: imprint timers, breeding windows, resource runs, raid-event timing, and recurring maintenance. Multi-Character Management tracks multiple ARK profiles/characters and safely switches between them.

## Scheduling Model

### Jobs
```rust
struct Job {
    id: JobId,
    name: String,
    trigger: Trigger,
    action: Action,            // Agent | Macro | NexusScript | Command
    profile: Option<ProfileId>,// which character profile this runs under
    guard: Option<Guard>,      // precondition: game state, inventory, time-of-day
    retry: RetryPolicy,
    enabled: bool,
    tags: Vec<String>,
}

enum Trigger {
    Cron(CronExpr),            // standard 5/6-field cron
    Interval(Duration),        // every X
    Event(EventSelector),      // world event: night start, raining, imprint timer ready
    Manual,                    // queued for user/agent
    OneShot(DateTime),
}
```

### Dispatch rules
- Triggers are evaluated by a **tick scheduler** (100ms); due jobs go into a priority queue.
- Priority: Event > Cron interval-critical (imprint) > OneShot > Manual > Interval > Cron.
- A job may only start when its **guard** passes (e.g., `game.online`, `player.inventory_open == false`, `agent.lease == none`).
- Coalescing: if a job is already running and its trigger fires again, it re-schedules a follow-up instead of stacking.

### Example job (imprint)
```json
{
  "id": "imprint-rex-01",
  "trigger": { "event": { "hud.imprint.available": true } },
  "action": { "agent": "Imprinter", "params": { "dino": "Rex 01" } },
  "profile": "main",
  "guard": { "game.online": true, "mode != Manual" },
  "retry": { "max": 2, "backoff_s": [15, 60] }
}
```

## Time Sources

- **Monotonic clock** for scheduling math (no NTP jumps).
- **Wall clock** for cron/event alignment (day/night in ARK map time).
- **Game-time events** (imprint ready, egg hatch, tame complete) come from the Vision HUD parser or the Knowledge DB timers, delivered as `Event` triggers.

## Multi-Character Management

### Profile model
```rust
struct Profile {
    id: ProfileId,
    name: String,
    launcher: LauncherCfg,     // steam launch args, dedicated server join cmd
    keybindings: Bindings,     // for games with per-char binds
    input_profile: InputProfile,
    agents_allowed: Vec<AgentKind>,
    storage_hints: StorageMap, // which containers are "base metal", etc.
}
```

### Switching
A **character switch** is a sequence (macro/script) that:
1. Saves/safe-logs the current character (or lets an offline timer handle it).
2. Launches/joins the target character's session.
3. Waits for the `game.online` vision guard.
4. Applies the target profile's input profile + bindings.
5. Reports ready.

The switch is interruptible; switching while an agent holds the input lease is refused (`guard: agent.lease == none`).

### Multi-instance
- Optional **multi-window** support (ARK supports one instance per launch config on many setups). Scheduler can target a specific game window handle; the Input Engine + Vision pipeline are bound to that window (see doc 04 capture config).
- The input engine supports per-window dispatch for foregrounded windows only, to avoid input going to the wrong instance.

## Failure Handling

- Missed trigger (PC asleep): on wake, run **catch-up**: evaluate missed jobs by policy (`run_now | skip | queue`).
- Character switch timeout: revert profile, alert user.
- Job crash loop: exponential backoff, cap consecutive failures, then disable + notify.

## Persistence

- Jobs and profiles stored in SQLite (`jobs`, `profiles`, `job_history`).
- Job history drives the Decision Engine's planning of future schedules (e.g., "imprint jobs that run within 10 min of boss fights get higher priority").
- All scheduling decisions are logged with reasons (audit + self-improvement).

## API Surface

```rust
impl Scheduler {
    fn upsert_job(&self, j: Job) -> Result<JobId>;
    fn trigger_now(&self, id: JobId) -> Result<()>;
    fn next_run(&self, id: JobId) -> Result<Option<DateTime>>;
    fn run_history(&self, id: JobId) -> Vec<JobRun>;
    fn switch_profile(&self, target: ProfileId) -> Result<SwitchHandle>;
    fn profiles(&self) -> Vec<Profile>;
}
```
