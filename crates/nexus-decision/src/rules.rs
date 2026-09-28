use serde::{Deserialize, Serialize};

/// A decision rule: when the situation matches, select a goal/plan.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Rule {
    pub id: String,
    pub when: Condition,
    pub goal: String,
    pub plan: String,
    pub priority: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct Condition {
    /// min value of a numeric blackboard key, e.g. ("inv.metal", 500) => metal >= 500
    pub ge: Vec<(String, f64)>,
    /// max value, e.g. ("inv.metal", 500) => metal < 500
    pub lt: Vec<(String, f64)>,
    /// boolean keys that must be true
    pub requires: Vec<String>,
    /// boolean keys that must be false
    pub excludes: Vec<String>,
}

impl Condition {
    pub fn matches(&self, ctx: &dyn Situation) -> bool {
        for (k, v) in &self.ge {
            if ctx.num(k).map(|x| x < *v).unwrap_or(true) {
                return false;
            }
        }
        for (k, v) in &self.lt {
            if ctx.num(k).map(|x| x >= *v).unwrap_or(false) {
                return false;
            }
        }
        for k in &self.requires {
            if !ctx.bool(k).unwrap_or(false) {
                return false;
            }
        }
        for k in &self.excludes {
            if ctx.bool(k).unwrap_or(false) {
                return false;
            }
        }
        true
    }
}

/// Minimal view of the world for rule evaluation.
pub trait Situation {
    fn num(&self, key: &str) -> Option<f64>;
    fn bool(&self, key: &str) -> Option<bool>;
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Ctx;
    impl Situation for Ctx {
        fn num(&self, key: &str) -> Option<f64> {
            match key {
                "inv.metal" => Some(1200.0),
                _ => None,
            }
        }
        fn bool(&self, key: &str) -> Option<bool> {
            match key {
                "world.night" => Some(false),
                "threat.near" => Some(true),
                _ => None,
            }
        }
    }

    #[test]
    fn rule_matches() {
        let r = Rule {
            id: "r1".into(),
            when: Condition {
                ge: vec![("inv.metal".into(), 1000.0)],
                lt: vec![("inv.metal".into(), 5000.0)],
                requires: vec!["threat.near".into()],
                excludes: vec!["world.night".into()],
            },
            goal: "store".into(),
            plan: "deposit".into(),
            priority: 1,
        };
        assert!(r.when.matches(&Ctx));
    }

    #[test]
    fn requires_false_rejects() {
        let r = Rule {
            id: "r3".into(),
            when: Condition {
                requires: vec!["world.night".into()],
                ..Default::default()
            },
            goal: "x".into(),
            plan: "y".into(),
            priority: 1,
        };
        assert!(!r.when.matches(&Ctx));
    }
}
