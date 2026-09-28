use crate::events::{InputError, InputEvent, ProducerKind};
use std::collections::VecDeque;

#[derive(Debug, Clone, PartialEq)]
pub enum EngineMode {
    Manual,
    Assisted,
    Autonomous,
}

/// Token bucket per producer to prevent macro storms.
#[derive(Debug, Clone)]
struct TokenBucket {
    tokens: f64,
    last_refill: f64,
    cap: f64,
    rate: f64,
}

impl TokenBucket {
    fn new(rate: f64, cap: f64) -> Self {
        Self {
            tokens: cap,
            last_refill: 0.0,
            cap,
            rate,
        }
    }

    fn try_take(&mut self, now: f64, n: f64) -> bool {
        self.refill(now);
        if self.tokens >= n {
            self.tokens -= n;
            true
        } else {
            false
        }
    }

    fn refill(&mut self, now: f64) {
        let elapsed = now - self.last_refill;
        if elapsed > 0.0 {
            self.tokens = (self.tokens + elapsed * self.rate).min(self.cap);
            self.last_refill = now;
        }
    }
}

/// The Input Engine: single gateway for all input. Arbitration + rate limiting.
#[derive(Debug)]
pub struct InputEngine {
    mode: EngineMode,
    tokens_per_sec: u64,
    buckets: std::collections::HashMap<String, TokenBucket>,
    pub queue: VecDeque<InputEvent>,
    pub kill_switch_engaged: bool,
    next_id: u64,
    pub log: Vec<InputEvent>,
}

impl Default for InputEngine {
    fn default() -> Self {
        Self::new(300)
    }
}

impl InputEngine {
    pub fn new(tokens_per_sec: u64) -> Self {
        Self {
            mode: EngineMode::Manual,
            tokens_per_sec,
            buckets: std::collections::HashMap::new(),
            queue: VecDeque::new(),
            kill_switch_engaged: false,
            next_id: 1,
            log: Vec::new(),
        }
    }

    pub fn set_mode(&mut self, m: EngineMode) {
        self.mode = m;
    }

    pub fn mode(&self) -> &EngineMode {
        &self.mode
    }

    pub fn engage_kill_switch(&mut self) {
        self.kill_switch_engaged = true;
        self.queue.clear();
        self.log.clear();
    }

    pub fn is_kill_switched(&self) -> bool {
        self.kill_switch_engaged
    }

    /// Send events. User and AgentEmergency always pass; others require
    /// Autonomous (or Assisted for Scheduler) mode and sufficient tokens.
    pub fn send(&mut self, events: Vec<InputEvent>, now: f64) -> Result<(), InputError> {
        if self.kill_switch_engaged {
            return Err(InputError::KillSwitch);
        }
        for ev in events {
            match ev.producer.0 {
                ProducerKind::User | ProducerKind::AgentEmergency => {}
                ProducerKind::Scheduler => {
                    if self.mode == EngineMode::Manual {
                        return Err(InputError::Denied(ev.producer.1.clone()));
                    }
                }
                ProducerKind::Macro | ProducerKind::Script => {
                    if self.mode != EngineMode::Autonomous && self.mode != EngineMode::Assisted {
                        return Err(InputError::Denied(ev.producer.1.clone()));
                    }
                }
            }
            let bucket = self
                .buckets
                .entry(ev.producer.1.clone())
                .or_insert_with(|| TokenBucket::new(self.tokens_per_sec as f64, 60.0));
            if !bucket.try_take(now, 1.0) {
                return Err(InputError::RateLimited(ev.producer.1.clone()));
            }
            let mut ev = ev;
            ev.id = self.next_id;
            self.next_id += 1;
            self.queue.push_back(ev.clone());
            self.log.push(ev);
        }
        Ok(())
    }

    /// Drain events sorted by producer priority (low number = high priority).
    pub fn drain(&mut self) -> Vec<InputEvent> {
        let mut out: Vec<InputEvent> = self.queue.drain(..).collect();
        out.sort_by_key(|e| e.producer.priority());
        out
    }

    /// Highest-priority pending producer (for arbitration).
    pub fn pending_priority(&self) -> Option<u8> {
        self.queue.iter().map(|e| e.producer.priority()).min()
    }

    pub fn queue_len(&self) -> usize {
        self.queue.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::events::{EventKind, ProducerId, ProducerKind};

    fn ev(p: ProducerId) -> InputEvent {
        InputEvent {
            id: 0,
            ts: 0.0,
            kind: EventKind::KeyDown { key: "W".into() },
            device: crate::events::Device::Virtual,
            producer: p,
        }
    }

    #[test]
    fn user_input_preempts_in_manual() {
        let mut eng = InputEngine::new(100);
        eng.set_mode(EngineMode::Manual);
        let user = ev(ProducerId::new(ProducerKind::User, "u"));
        assert!(eng.send(vec![user], 1.0).is_ok());
    }

    #[test]
    fn macro_denied_in_manual() {
        let mut eng = InputEngine::new(100);
        eng.set_mode(EngineMode::Manual);
        let m = ev(ProducerId::new(ProducerKind::Macro, "farm"));
        assert_eq!(
            eng.send(vec![m], 1.0),
            Err(InputError::Denied("farm".into()))
        );
    }

    #[test]
    fn kill_switch_flushes_and_blocks() {
        let mut eng = InputEngine::new(100);
        eng.set_mode(EngineMode::Autonomous);
        let m = ev(ProducerId::new(ProducerKind::Macro, "farm"));
        assert!(eng.send(vec![m.clone()], 1.0).is_ok());
        eng.engage_kill_switch();
        assert_eq!(eng.queue_len(), 0);
        assert_eq!(eng.send(vec![m], 2.0), Err(InputError::KillSwitch));
    }

    #[test]
    fn token_bucket_limits_burst() {
        let mut eng = InputEngine::new(1); // 1 token/sec
        eng.set_mode(EngineMode::Autonomous);
        let m = ProducerId::new(ProducerKind::Script, "spam");
        // burst cap is 60; events sent at the same instant exceed it
        let mut ok = 0;
        for _ in 0..100 {
            let e = ev(m.clone());
            if eng.send(vec![e], 100.0).is_ok() {
                ok += 1;
            } else {
                break;
            }
        }
        assert_eq!(ok, 60);
    }

    #[test]
    fn drain_sorts_by_priority() {
        let mut eng = InputEngine::new(1000);
        eng.set_mode(EngineMode::Autonomous);
        let script = ev(ProducerId::new(ProducerKind::Script, "s"));
        let m = ev(ProducerId::new(ProducerKind::Macro, "m"));
        eng.send(vec![script, m], 1.0).unwrap();
        let drained = eng.drain();
        assert_eq!(drained[0].producer.0, ProducerKind::Macro);
        assert_eq!(drained[1].producer.0, ProducerKind::Script);
    }
}
