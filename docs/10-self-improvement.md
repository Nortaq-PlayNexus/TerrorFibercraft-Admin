# 10 — Self-Improvement

## Purpose

Self-Improvement makes NEXUS get better over time. It learns from **telemetry** — its own executed actions, verifications, failures, and outcomes — and adjusts parameters and strategies. It is deliberately conservative: it tunes *behavior parameters* (durations, thresholds, plan weights) and does **not** mutate neural weights or blindly rewrite user scripts.

## Principles

1. **Tune, don't rewrite** — adjust documented parameters, not code structure.
2. **Measured, not imagined** — every change is backed by a statistically meaningful improvement on tracked metrics.
3. **Reversible** — every tuning decision is an audited record; one-click revert.
4. **Constrained** — improvements must respect the safety model (docs 01–09).

## Telemetry Pipeline

```
Input events, Vision results, Macro ReplayReports,
Agent verifications, Decision traces, Job runs, Script traces
        |
        v
  Telemetry store (SQLite, append-only, TTL retention)
        |
        v
  Feature extraction (offline job)
        |
        v
  Metric computation -> per (action, context) stats
        |
        v
  Tuning candidates (offline job) -> review -> apply
```

### Key metrics
- **Macro timing error** p50/p95 (doc 02).
- **Vision confidence** per class/layout; stale-track rate.
- **Agent success rate** per action type and context.
- **Tame/boss success** rates with risk model priors (doc 08).
- **Scheduler punctuality** and missed-trigger rate.

## What Can Be Adjusted

| Parameter | Owner | Example adjustment |
|---|---|---|
| `snap_ms` (macro clean) | Macro Engine | lower when timing error high |
| latency safety margin | Input Engine | raise during spikes |
| sensitivity curve | Input Engine | per-profile calibration |
| YOLO conf threshold per class | Vision | tune NMS/conf on precision-recall |
| OCR region cache | Vision | add/refresh ROI cache |
| BT retry counts, backoff | Agent Framework | based on failure-class frequency |
| Decision weights (reward/cost/risk) | Decision Engine | re-prioritize winning plans |
| Schedule job priorities | Scheduler | promote critical recurring jobs |
| Plan confidence threshold | Decision Engine | per-context escalation |

### Never adjusted automatically
- User-authored scripts/macros (except parameter suggestions, user-applied).
- Capabilities / permission grants.
- Anything that lowers safety guarantees.

## Learning Loop

1. **Collect**: telemetry flows in with `correlation_id` linking decision → plan → actions → verification → outcome.
2. **Extract features**: group by `(action_kind, context_hash)` where context = situation vector bucket (doc 08).
3. **Compute stats**: success rate, timing stats, distributions; require minimum sample size (e.g., ≥30 executions) before trusting.
4. **Generate candidates**: parameter change proposals with expected effect, e.g. "raise `narcotic_refill_pct` from 60→65 because torpor drops were responsible for 12% of tame failures."
5. **Validate**: simulate against recent history (offline replay of telemetry with new params) — the change must improve the metric in simulation.
6. **Apply**: write to a `tunings` table with before/after + reason + rollback info; notify user in the UI ("NEXUS tuned narcotic refill: 60% → 65%, est. +4% tame success").
7. **Monitor**: new telemetry confirms (or refutes) the expected effect; refuted tunings are reverted or adjusted.

## Reward Signals

- Explicit: user ratings ("that run went well/badly" on a macro/agent run).
- Implicit: telemetry outcomes (harvest yield, tame success, no deaths, on-schedule).
- Proxy: resource/hr, maturating% vs expected, imprint coverage.

## Decision Engine Feedback

- Risk model priors are refreshed from telemetry: `p(death | action, context)` per unit class and action.
- Plan scores become more accurate; the LLM planner's few-shot examples include recent successful plan traces.

## Governance & Controls

- **Master switch**: enable/disable Self-Improvement entirely.
- **Scope**: choose which domains may auto-tune (macros / vision / agents / scheduler / decisions).
- **Budgets**: max number of auto-applied tunings per week; all reversible.
- **Audit trail**: every applied tuning has a full record (id, param, from→to, reason, telemetry refs, sim result, applied_ts, status).

## API Surface

```rust
impl SelfImprovement {
    fn metrics(&self, window: Window) -> Result<Vec<Metric>>;
    fn candidates(&self) -> Result<Vec<TuningCandidate>>;
    fn apply(&self, t: TuningCandidate) -> Result<()>;
    fn rollback(&self, tuning_id: u64) -> Result<()>;
    fn status(&self) -> SIStatus;
}
```
