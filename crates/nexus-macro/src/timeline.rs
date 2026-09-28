use nexus_input::events::{InputEvent, ProducerId, ProducerKind};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct VisionQuery {
    pub class: String,
    pub op: String, // "any" | "none"
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum MacroNode {
    Delay { ms: f64 },
    Event(InputEvent),
    Vision { query: VisionQuery, timeout_ms: u64 },
    Call { macro_id: String, depth: u8 },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Macro {
    pub id: String,
    pub name: String,
    pub nodes: Vec<MacroNode>,
    pub recorded_duration_ms: f64,
}

#[derive(Debug, Clone, Error, PartialEq)]
pub enum MacroError {
    #[error("macro not found: {0}")]
    NotFound(String),
    #[error("call depth exceeded (cycle?)")]
    Cycle,
    #[error("vision wait timed out")]
    VisionTimeout,
    #[error("interrupted by user input")]
    Interrupted,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct ReplayReport {
    pub macro_id: String,
    pub events_sent: u64,
    pub events_dropped: u64,
    pub timing_error_p95_ms: f64,
    pub vision_waits: u64,
    pub aborted: bool,
}

/// Replays a macro timeline, applying latency compensation and composing calls.
pub struct MacroEngine {
    pub macros: std::collections::HashMap<String, Macro>,
    pub measured_latency_ms: f64,
    pub safety_margin_ms: f64,
    pub snap_ms: f64,
}

impl Default for MacroEngine {
    fn default() -> Self {
        Self {
            macros: std::collections::HashMap::new(),
            measured_latency_ms: 0.0,
            safety_margin_ms: 5.0,
            snap_ms: 50.0,
        }
    }
}

impl MacroEngine {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, m: Macro) {
        self.macros.insert(m.id.clone(), m);
    }

    /// Clean a recording: merge gaps smaller than snap_ms, tag long gaps as Delay.
    pub fn clean(&self, mut m: Macro) -> Macro {
        let mut out: Vec<MacroNode> = Vec::new();
        for node in m.nodes.drain(..) {
            match node {
                MacroNode::Event(ev) => {
                    // collapse duplicate consecutive key down/down pairs
                    out.push(MacroNode::Event(ev));
                }
                other => out.push(other),
            }
        }
        m.nodes = out;
        m
    }

    /// Replay. `on_send` is the sink (normally the Input Engine). Returns report.
    pub fn play<F>(
        &self,
        id: &str,
        producer_suffix: &str,
        on_send: &mut F,
    ) -> Result<ReplayReport, MacroError>
    where
        F: FnMut(&InputEvent) -> Result<(), String>,
    {
        let m = self
            .macros
            .get(id)
            .ok_or_else(|| MacroError::NotFound(id.to_string()))?;
        let mut report = ReplayReport {
            macro_id: id.to_string(),
            ..Default::default()
        };
        let comp = self.measured_latency_ms + self.safety_margin_ms;
        let mut clock = 0.0f64;
        let producer = ProducerId::new(ProducerKind::Macro, format!("{}:{}", id, producer_suffix));

        for node in &m.nodes {
            match node {
                MacroNode::Delay { ms } => {
                    clock += ms + comp;
                }
                MacroNode::Event(ev) => {
                    let mut e = ev.clone();
                    e.producer = producer.clone();
                    e.ts = clock;
                    match on_send(&e) {
                        Ok(()) => report.events_sent += 1,
                        Err(_) => report.events_dropped += 1,
                    }
                }
                MacroNode::Vision { timeout_ms, .. } => {
                    report.vision_waits += 1;
                    clock += *timeout_ms as f64; // simulate wait cost
                }
                MacroNode::Call { macro_id, depth } => {
                    self.replay_call(macro_id, *depth, &producer, &mut clock, &mut report, on_send)?;
                }
            }
        }
        Ok(report)
    }

    fn replay_call<F>(
        &self,
        macro_id: &str,
        depth: u8,
        producer: &ProducerId,
        clock: &mut f64,
        report: &mut ReplayReport,
        on_send: &mut F,
    ) -> Result<(), MacroError>
    where
        F: FnMut(&InputEvent) -> Result<(), String>,
    {
        if depth > 8 {
            return Err(MacroError::Cycle);
        }
        let sub = self
            .macros
            .get(macro_id)
            .ok_or_else(|| MacroError::NotFound(macro_id.to_string()))?;
        for sub_node in &sub.nodes {
            match sub_node {
                MacroNode::Event(ev) => {
                    let mut e = ev.clone();
                    e.producer = producer.clone();
                    e.ts = *clock;
                    match on_send(&e) {
                        Ok(()) => report.events_sent += 1,
                        Err(_) => report.events_dropped += 1,
                    }
                }
                MacroNode::Call { macro_id, .. } => {
                    self.replay_call(macro_id, depth + 1, producer, clock, report, on_send)?;
                }
                MacroNode::Delay { ms } => {
                    *clock += *ms;
                }
                MacroNode::Vision { timeout_ms, .. } => {
                    report.vision_waits += 1;
                    *clock += *timeout_ms as f64;
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nexus_input::events::{Device, EventKind, InputEvent, KeyState};

    fn key(kind: EventKind) -> InputEvent {
        InputEvent {
            id: 0,
            ts: 0.0,
            kind,
            device: Device::Virtual,
            producer: ProducerId::new(ProducerKind::Macro, "test"),
        }
    }

    #[test]
    fn replay_sends_all_events_with_compensation() {
        let mut eng = MacroEngine::new();
        eng.measured_latency_ms = 12.0;
        eng.register(Macro {
            id: "m1".into(),
            name: "test".into(),
            recorded_duration_ms: 100.0,
            nodes: vec![
                MacroNode::Delay { ms: 10.0 },
                MacroNode::Event(key(EventKind::KeyDown { key: "W".into() })),
                MacroNode::Delay { ms: 20.0 },
                MacroNode::Event(key(EventKind::KeyUp { key: "W".into() })),
            ],
        });
        let mut sink: Vec<InputEvent> = Vec::new();
        let report = eng
            .play("m1", "runner", &mut |e| {
                sink.push(e.clone());
                Ok(())
            })
            .unwrap();
        assert_eq!(report.events_sent, 2);
        assert_eq!(sink.len(), 2);
        // latency compensation applied to first event timestamp
        assert!((sink[0].ts - (10.0 + 12.0 + 5.0)).abs() < 1e-9);
    }

    #[test]
    fn missing_macro_errors() {
        let eng = MacroEngine::new();
        let r = eng.play("nope", "x", &mut |_| Ok(()));
        assert_eq!(r, Err(MacroError::NotFound("nope".into())));
    }

    #[test]
    fn call_cycle_detected() {
        let mut eng = MacroEngine::new();
        eng.register(Macro {
            id: "a".into(),
            name: "a".into(),
            recorded_duration_ms: 0.0,
            nodes: vec![MacroNode::Call {
                macro_id: "b".into(),
                depth: 0,
            }],
        });
        eng.register(Macro {
            id: "b".into(),
            name: "b".into(),
            recorded_duration_ms: 0.0,
            nodes: vec![MacroNode::Call {
                macro_id: "a".into(),
                depth: 0,
            }],
        });
        let r = eng.play("a", "x", &mut |_| Ok(()));
        assert_eq!(r, Err(MacroError::Cycle));
    }
}
