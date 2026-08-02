use crate::rules::{Rule, Situation};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RankedPlan {
    pub plan: String,
    pub score: f64,
    pub reward: f64,
    pub cost: f64,
    pub risk_penalty: f64,
    pub reasons: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Decision {
    pub goal: String,
    pub plan: String,
    pub confidence: f64,
    pub chosen_by_rule: bool,
    pub ranked: Vec<RankedPlan>,
}

#[derive(Debug, Clone)]
pub struct Candidate {
    pub plan: String,
    pub reward: f64,
    pub cost: f64,
    pub risk: f64,
}

/// Linear cost model: score = reward - cost - risk_penalty.
#[derive(Debug, Clone)]
pub struct CostModel {
    pub weight_reward: f64,
    pub weight_cost: f64,
    pub weight_risk: f64,
}

impl Default for CostModel {
    fn default() -> Self {
        Self {
            weight_reward: 1.0,
            weight_cost: 1.0,
            weight_risk: 1.0,
        }
    }
}

impl CostModel {
    pub fn score(&self, c: &Candidate) -> f64 {
        self.weight_reward * c.reward - self.weight_cost * c.cost - self.weight_risk * c.risk
    }
}

/// The Decision Engine: rules first, then cost model over candidates.
pub struct DecisionEngine {
    pub rules: Vec<Rule>,
    pub model: CostModel,
    pub confidence_threshold: f64,
}

impl Default for DecisionEngine {
    fn default() -> Self {
        Self {
            rules: Vec::new(),
            model: CostModel::default(),
            confidence_threshold: 0.7,
        }
    }
}

impl DecisionEngine {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_rule(&mut self, r: Rule) {
        self.rules.push(r);
    }

    /// Evaluate a user goal against the situation, returning a decision.
    /// Priority: matching rules (highest priority wins), else best candidate.
    pub fn evaluate(&self, goal: &str, ctx: &dyn Situation, candidates: &[Candidate]) -> Decision {
        let mut rules: Vec<&Rule> = self
            .rules
            .iter()
            .filter(|r| r.goal == goal && r.when.matches(ctx))
            .collect();
        rules.sort_by_key(|r| std::cmp::Reverse(r.priority));

        if let Some(r) = rules.first() {
            // rule-based: confidence from rule priority / closeness
            let confidence = (r.priority as f64 / 10.0).clamp(0.0, 1.0).max(0.5);
            let ranked: Vec<RankedPlan> = candidates
                .iter()
                .map(|c| RankedPlan {
                    plan: c.plan.clone(),
                    score: self.model.score(c),
                    reward: c.reward,
                    cost: c.cost,
                    risk_penalty: c.risk,
                    reasons: vec![format!("rule {} fired", r.id)],
                })
                .collect();
            return Decision {
                goal: goal.into(),
                plan: r.plan.clone(),
                confidence,
                chosen_by_rule: true,
                ranked,
            };
        }

        // cost-model path
        let mut ranked: Vec<RankedPlan> = candidates
            .iter()
            .map(|c| RankedPlan {
                plan: c.plan.clone(),
                score: self.model.score(c),
                reward: c.reward,
                cost: c.cost,
                risk_penalty: c.risk,
                reasons: vec!["cost model".into()],
            })
            .collect();
        ranked.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));

        let best = ranked.first().cloned();
        let (plan, confidence) = match best {
            Some(b) => {
                let spread = ranked
                    .first()
                    .zip(ranked.get(1))
                    .map(|(a, b)| (a.score - b.score).abs())
                    .unwrap_or(1.0);
                let conf = (b.score / (b.score.abs() + 1.0) + spread * 0.5)
                    .clamp(0.0, 1.0);
                (b.plan.clone(), conf)
            }
            None => ("wait".into(), 0.0),
        };

        Decision {
            goal: goal.into(),
            plan,
            confidence,
            chosen_by_rule: false,
            ranked,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::rules::Condition;

    struct Ctx;
    impl Situation for Ctx {
        fn num(&self, k: &str) -> Option<f64> {
            match k {
                "inv.metal" => Some(300.0),
                _ => None,
            }
        }
        fn bool(&self, k: &str) -> Option<bool> {
            match k {
                "world.night" => Some(false),
                _ => None,
            }
        }
    }

    fn candidates() -> Vec<Candidate> {
        vec![
            Candidate {
                plan: "farm_rush".into(),
                reward: 10.0,
                cost: 4.0,
                risk: 1.0,
            },
            Candidate {
                plan: "idle".into(),
                reward: 0.0,
                cost: 0.0,
                risk: 0.0,
            },
        ]
    }

    #[test]
    fn rule_wins_when_matching() {
        let mut de = DecisionEngine::new();
        de.add_rule(Rule {
            id: "low_metal".into(),
            when: Condition {
                lt: vec![("inv.metal".into(), 500.0)],
                requires: vec![],
                excludes: vec!["world.night".into()],
                ge: vec![],
            },
            goal: "metal".into(),
            plan: "farm_rush".into(),
            priority: 5,
        });
        let d = de.evaluate("metal", &Ctx, &candidates());
        assert!(d.chosen_by_rule);
        assert_eq!(d.plan, "farm_rush");
    }

    #[test]
    fn cost_model_picks_best_without_rules() {
        let de = DecisionEngine::new();
        let d = de.evaluate("metal", &Ctx, &candidates());
        assert!(!d.chosen_by_rule);
        assert_eq!(d.plan, "farm_rush");
        assert!(d.ranked[0].score > d.ranked[1].score);
    }

    #[test]
    fn risk_penalty_flips_choice() {
        let de = DecisionEngine {
            model: CostModel {
                weight_risk: 10.0,
                ..Default::default()
            },
            ..Default::default()
        };
        let d = de.evaluate("metal", &Ctx, &candidates());
        assert_eq!(d.plan, "idle");
    }

    #[test]
    fn no_candidates_yields_wait() {
        let de = DecisionEngine::new();
        let d = de.evaluate("metal", &Ctx, &[]);
        assert_eq!(d.plan, "wait");
    }
}
