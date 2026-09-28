# 05 — Agent Framework

## Purpose

The Agent Framework runs autonomous behaviors. Agents are goal-driven controllers that decide what to do (plan), act through the Input Engine, verify via Vision, and adapt. The framework provides the runtime, the shared **Blackboard**, and a library of reusable behavior nodes.

## Core Concepts

### Agent
```rust
struct Agent {
    id: AgentId,
    kind: AgentKind,          // Farmer, Breeder, Tamer, Scout, Imprinter, BossPrep, ResourceRunner
    profile: AgentProfile,    // grants, target, params, confidence thresholds
    tree: BehaviorTree,
    state: AgentState,        // Idle | Planning | Acting | Verifying | Waiting | Blocked | Paused | Killed
    budget: Budget,           // time, actions, failures allowed
}
```

### Blackboard (shared, versioned)
- A single source of truth for the world + user + system state.
- Written by: Vision snapshoter, Decision Engine, Knowledge DB, agents (their own section), user (overrides).
- Namespaced keys: `world.weather`, `inv.metal`, `agent.farmer.plan`, `user.goal`.
- Every write is timestamped; readers use staleness-aware accessors.
- Persisted periodically so a crash can be resumed.

### Behavior Trees
Standard BT with:
- Decorators: `Retry`, `Timeout`, `Repeater`, `Guard(capability)`, `Lock`.
- Selectors/Sequences/Parallel with `Failure`/`Success`/`Running`.
- **Leaf actions** are thin wrappers over: Input Engine (`attack`, `move_to`), NexusScript (arbitrary scripted subtask), Vision waits (`confirm: dino_dead`), Knowledge queries (`recipe: refined_ingot`).

### The Observe–Orient–Decide–Act (OODA) loop
Each agent tick (e.g., 100ms):
1. **Observe**: pull fresh Blackboard vision snapshot.
2. **Orient**: reconcile with beliefs; update its local world model.
3. **Decide**: run BT tick; if a plan is missing/stale, call Planner.
4. **Act**: emit one bounded action bundle → Input Engine; record telemetry.

## Planner (LLM-assisted)

- Deterministic-first: BT pick from a library of plans; the **Decision Engine** (doc 08) selects.
- If no rule matches or uncertainty > threshold, a **planner prompt** is sent to the Model Runtime (doc 11):
  - Input: blackboard slice + available plans + goal + history.
  - Output: a plan (structured JSON) validated by schema → compiled to a BT or NexusScript, then `nexus check`.
- Planner output is always validated; never executed raw. Validation = capability check + liveness check + schema check.

## Verification ("act → verify → act")

Every critical action has a **verifier**:
- `verify_after(action, predicate, timeout)`.
- Predicates: vision (`dino_at`, `weight_dropped`, `inventory_opened`), OCR (`count_matched`), telemetry (`event: key_down:pick`).
- On verification failure: retry (with backoff), then degrade to a fallback sub-plan, then emit `Blocked` + alert to user.
- Failures are classified and logged as structured signals for Self-Improvement (doc 10).

## Agent Catalog (v1)

| Agent | Goal | Vision deps | Input deps | Notes |
|---|---|---|---|---|
| Farmer | gather X resource/hour | resource nodes, weight, HUD | move/attack/pick | uses Knowledge DB node locations |
| ResourceRunner | transport to/from storage | inventory OCR, coords | nav, deposit | path optimization via Decision Engine |
| Breeder | maintain breeding pairs, egg/hatch | maturation %, egg on ground | pickup, transfer | maturation timers |
| Tamer | knock out + feed tame | taming %, torpor bar | darts, narcotics, food | highest-stakes, most guards |
| Imprinter | imprint on schedule | imprint %, timer | feed/ride | driven by Scheduler mostly |
| Scout | survey area / find dino | dino classes, coords | move | writes findings to Blackboard/DB |
| BossPrep | prepare artifacts/items/tames | inventory, tames | craft, collect | orchestrated by Decision Engine |
| Builder | place structures per blueprint | placement ghost color | place/rotate | blueprint from KB/base-design |

## Concurrency & Arbitration

- One agent **owns** the Input Engine at a time (input arbitration from doc 01). Agents cooperate via Blackboard leases: `lease:input = agent.farmer` with TTL.
- Multiple agents may run concurrently when vision-only or low-interference, but only one uses input.
- Kill-switch / user input preempts all agents (doc 01).

## Safety & Liveness

- Every agent has a **budget**: max wall time, max actions, max consecutive failures → auto-pause + report.
- **Panic state**: if an action attempts to fight a wild giga with a dodo, Decision Engine cost model should reject the plan *before* execution; vision `warnings` gate risky moves.
- Agents never execute marketplace scripts silently; generated/scripted subtasks go through `nexus check` (doc 03).
- Full audit trail per agent run: plan, actions, verifications, deviations — stored for replay.

## API Surface

```rust
impl AgentRuntime {
    fn spawn(&self, agent: Agent) -> Result<AgentHandle>;
    fn pause(&self, id) -> Result<()>;
    fn resume(&self, id) -> Result<()>;
    fn kill(&self, id) -> Result<()>;
    fn status(&self) -> Vec<AgentStatus>;
    fn blackboard(&self) -> &Blackboard;
    fn grant(&self, id, cap: Capability, scope: Scope) -> Result<()>;
}
```
