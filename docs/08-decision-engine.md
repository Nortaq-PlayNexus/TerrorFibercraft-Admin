# 08 — Decision Engine

## Purpose

The Decision Engine chooses **what to do next** given goals, world state, knowledge, and risk. It is the "purpose" layer: it turns "I want more metal" into a prioritized, costed, safe plan. It blends deterministic rules with a cost model and an LLM fallback for ambiguous or novel situations.

## Role Boundaries

- **Inputs**: Blackboard snapshot, Knowledge DB lookups, telemetry stats, user goals, agent capability declarations.
- **Outputs**: a chosen **Goal** and its **Plan** (steps), plus a confidence score and reasons.
- **Does NOT** execute input directly — plans go to Agent Framework (05) or NexusScript (03).

## Architecture

```
                     +----------------+   +---------------------+
   Blackboard  ----->|                |   |  Knowledge DB       |
   Telemetry   ----->|  Situation     |-->|  (recipes, yields,  |
   User goals  ----->|  Assessment    |   |   locations, risk)  |
                     +----------------+   +---------------------+
                              |
                              v
                     +----------------+        +----------------+
                     |  Rule Engine   |------->|  Plan Library  |
                     | (decision      |        | (candidate     |
                     |  tables/rules) |        |  plans)        |
                     +----------------+        +----------------+
                              |
                     confidence < threshold?
                              |
                     +----------------+  (yes) +----------------+
                     |                |------->|  LLM Planner   |
                     | Cost Model     |        | (doc 11)       |
                     | (risk, time,   |        +----------------+
                     |  reward)       |
                     +----------------+
                              |
                              v
                     +----------------+
                     |  Plan Validator| -> capability, liveness, safety
                     +----------------+
                              |
                              v
                     +----------------+
                     |  Emit: Goal +  |
                     |  Plan + conf   |
                     +----------------+
```

## Situation Assessment

Computes a compact "situation vector" used by rules:
- Supplies: current inventory of key resources (from KB storage reads + OCR).
- Fleet: owned tames available (KB `my_tames`), their roles.
- Threats: wild dino tracks near base (vision), boss windows.
- Time: game time, event timing (rain, night, imprint due).
- Health: HP/stamina/weight (vision HUD).
- Priorities: user-set goals, pending jobs (scheduler), overdue imprints.

## Rule Engine

Decision tables (JSON, editable in UI):
```json
{
  "rule": "farm-when-low",
  "when": { "inv.metal": "<", 500, "world.night": false, "threat.near": "none" },
  "then": { "goal": "farm.metal", "priority": 3, "plan": "farm_metal_rush" }
}
```
- Rules are evaluated top-down; first match wins. Deterministic, auditable, fast.
- Rule conflicts are caught at load time (overlapping `when`).

## Cost Model

For each candidate plan, compute a score and pick the best:
```
score(plan) = Σ reward_i * w_i − Σ cost_j * c_j − risk_penalty
```
- **Rewards**: expected yield (KB yields × confirmed nodes), progress toward goal, time to boss/event.
- **Costs**: time estimate (distance/nav + gather + craft), consumables used, tame risk of death.
- **Risk**: expected value loss = probability(unit dies) × value(unit). Probability from telemetry of similar actions (doc 10) or conservative priors from KB.
- The model emits per-plan scores and reasons; UI shows a ranked list with "why".

## LLM Planner (fallback)

Used when:
- No rule matches, or confidence < threshold (default 0.7).
- Novel request: "prepare for the Island boss with what I have".
- Ambiguity: user gives natural-language goal.

Prompt construction:
- System: role + constraints + capability manifest (what agent may do).
- Context: situation vector (truncated), available plans, KB-relevant slices.
- Output schema: `{ "goal": str, "plan": [{ "step", "kind": "macro|script|agent", "ref" }], "confidence": 0-1 }`.
- **Validation**: schema check → capability check → `nexus check` for scripts → liveness check. Invalid output → reject + fall back to top rule plan + notify.

LLM never picks destructive unrequested goals; goal scope is always within the user's granted goal set.

## Confidence & Escalation

- `conf >= 0.7`: execute autonomously (in Autonomous mode).
- `0.4 <= conf < 0.7`: execute but log; surface "proceed?" toast in Assisted mode.
- `conf < 0.4`: do not execute; ask user or take safe default (wait, maintain, restock).

## Auditing

Every decision records: situation vector, rules fired, candidate scores, chosen plan, validator results, and outcome (from telemetry). This enables self-improvement (doc 10) and replay/debug.

## API Surface

```rust
impl DecisionEngine {
    fn evaluate(&self, goal: UserGoal) -> Result<Decision>;
    fn candidates(&self, goal: UserGoal) -> Result<Vec<RankedPlan>>;
    fn explain(&self, decision_id: DecisionId) -> Result<DecisionTrace>;
    fn update_models(&self, priors: &TelemetryStats) -> Result<()>; // from doc 10
    fn list_rules(&self) -> Vec<Rule>;     // editable via UI
}
```
