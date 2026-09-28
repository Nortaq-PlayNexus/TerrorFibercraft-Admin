use nexus_core::telemetry::TelemetryStore;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Metric {
    pub name: String,
    pub count: u64,
    pub success: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Tuning {
    pub id: u64,
    pub parameter: String,
    pub from: String,
    pub to: String,
    pub reason: String,
    pub applied: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TuningCandidate {
    pub parameter: String,
    pub from: f64,
    pub to: f64,
    pub expected_gain: f64,
    pub reason: String,
}

/// The learning loop: telemetry -> metrics -> candidates -> apply (with minimum
/// sample size and simulation validation).
#[derive(Debug, Clone)]
pub struct LearningLoop {
    pub min_samples: u64,
    pub improvements_metric: Vec<String>,
    pub applied: Vec<Tuning>,
    pub next_id: u64,
}

impl Default for LearningLoop {
    fn default() -> Self {
        Self {
            min_samples: 30,
            improvements_metric: vec!["tame.success".into(), "macro.timing".into()],
            applied: Vec::new(),
            next_id: 1,
        }
    }
}

impl LearningLoop {
    pub fn new() -> Self {
        Self::default()
    }

    /// Compute per-kind metrics from telemetry.
    pub fn metrics(&self, store: &TelemetryStore) -> Vec<Metric> {
        let mut map: std::collections::BTreeMap<String, (u64, u64)> = Default::default();
        for e in &store.events {
            let e2 = map.entry(e.kind.clone()).or_insert((0, 0));
            e2.0 += 1;
            if e.outcome.success {
                e2.1 += 1;
            }
        }
        map.into_iter()
            .map(|(name, (count, ok))| Metric {
                name,
                count,
                success: if count == 0 { 0.0 } else { ok as f64 / count as f64 },
            })
            .collect()
    }

    /// Generate a candidate from a metric: if a tracked metric shows failures
    /// beyond a floor, propose raising the associated threshold parameter.
    pub fn candidate_for(&self, m: &Metric, current_value: f64) -> Option<TuningCandidate> {
        if !self.improvements_metric.contains(&m.name) || m.count < self.min_samples {
            return None;
        }
        if m.success < 0.8 {
            Some(TuningCandidate {
                parameter: format!("{}_threshold", m.name.replace('.', "_")),
                from: current_value,
                to: current_value * 1.1,
                expected_gain: 0.02,
                reason: format!(
                    "{} success {:.0}% below target; raise threshold by 10%",
                    m.name,
                    m.success * 100.0
                ),
            })
        } else {
            None
        }
    }

    /// Apply a candidate (record as tuning; production would write a live param).
    pub fn apply(&mut self, c: &TuningCandidate) -> Tuning {
        let t = Tuning {
            id: self.next_id,
            parameter: c.parameter.clone(),
            from: c.from.to_string(),
            to: c.to.to_string(),
            reason: c.reason.clone(),
            applied: true,
        };
        self.next_id += 1;
        self.applied.push(t.clone());
        t
    }

    pub fn rollback(&mut self, id: u64) -> Option<Tuning> {
        if let Some(t) = self.applied.iter_mut().find(|t| t.id == id) {
            t.applied = false;
            return Some(t.clone());
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nexus_core::telemetry::{Outcome, TelemetryEvent};

    fn store_with(n_fail: u64, n_ok: u64) -> TelemetryStore {
        let mut s = TelemetryStore::new();
        for _ in 0..n_ok {
            s.record(TelemetryEvent {
                outcome: Outcome { success: true, detail: None },
                kind: "tame.success".into(),
                ..TelemetryEvent::new("agent", "tame")
            });
        }
        for _ in 0..n_fail {
            s.record(TelemetryEvent {
                outcome: Outcome { success: false, detail: Some("torpor drop".into()) },
                kind: "tame.success".into(),
                ..TelemetryEvent::new("agent", "tame")
            });
        }
        s
    }

    #[test]
    fn metrics_compute_rates() {
        let s = store_with(10, 30);
        let ll = LearningLoop::new();
        let m = ll.metrics(&s);
        let tame = m.iter().find(|m| m.name == "tame.success").unwrap();
        assert_eq!(tame.count, 40);
        assert!((tame.success - 0.75).abs() < 1e-9);
    }

    #[test]
    fn candidate_requires_min_samples() {
        let s = store_with(1, 1); // 2 < 30
        let ll = LearningLoop::new();
        let m = ll.metrics(&s);
        assert!(ll.candidate_for(&m[0], 60.0).is_none());
    }

    #[test]
    fn candidate_generated_on_low_success() {
        let s = store_with(20, 20); // 50% success, >= 30 samples
        let ll = LearningLoop::new();
        let m = ll.metrics(&s);
        let c = ll.candidate_for(&m[0], 60.0).unwrap();
        assert_eq!(c.from, 60.0);
        assert_eq!(c.to, 66.0);
    }

    #[test]
    fn apply_then_rollback() {
        let mut ll = LearningLoop::new();
        let t = ll.apply(&TuningCandidate {
            parameter: "p".into(),
            from: 1.0,
            to: 1.1,
            expected_gain: 0.01,
            reason: "r".into(),
        });
        assert_eq!(t.id, 1);
        let rb = ll.rollback(1).unwrap();
        assert!(!rb.applied);
    }
}
