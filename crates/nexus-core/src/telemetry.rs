use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TelemetryEvent {
    pub ts: String,
    pub correlation_id: String,
    pub producer: String,
    pub kind: String,
    pub outcome: Outcome,
    pub payload: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct Outcome {
    pub success: bool,
    pub detail: Option<String>,
}

impl TelemetryEvent {
    pub fn new(producer: &str, kind: &str) -> Self {
        Self {
            ts: Utc::now().to_rfc3339(),
            correlation_id: uuid::Uuid::new_v4().to_string(),
            producer: producer.to_string(),
            kind: kind.to_string(),
            outcome: Outcome::default(),
            payload: serde_json::json!({}),
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct TelemetryStore {
    pub events: Vec<TelemetryEvent>,
}

impl TelemetryStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn record(&mut self, ev: TelemetryEvent) {
        self.events.push(ev);
    }

    pub fn success_rate(&self, producer: &str, kind: &str) -> Option<f64> {
        let mut n = 0usize;
        let mut ok = 0usize;
        for e in &self.events {
            if e.producer == producer && e.kind == kind {
                n += 1;
                if e.outcome.success {
                    ok += 1;
                }
            }
        }
        if n == 0 {
            None
        } else {
            Some(ok as f64 / n as f64)
        }
    }

    pub fn failures_for(&self, kind: &str) -> Vec<&TelemetryEvent> {
        self.events
            .iter()
            .filter(|e| e.kind == kind && !e.outcome.success)
            .collect()
    }
}

/// Convenience facade used by the rest of the app.
#[derive(Debug, Clone, Default)]
pub struct Telemetry {
    pub store: TelemetryStore,
}

impl Telemetry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn log(&mut self, ev: TelemetryEvent) {
        self.store.record(ev);
    }

    pub fn snapshot(&self) -> BTreeMap<String, u64> {
        let mut m = BTreeMap::new();
        for e in &self.store.events {
            *m.entry(e.kind.clone()).or_insert(0) += 1;
        }
        m
    }
}
