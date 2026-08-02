use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Trigger {
    Cron(String),
    Interval(DurationSec),
    OneShot(DateTime<Utc>),
    Event(String),
    Manual,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct DurationSec(pub u64);

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct Guard {
    /// blackboard keys that must exist and be true
    pub requires: Vec<String>,
    /// blackboard keys that must not be true
    pub excludes: Vec<String>,
}

impl Guard {
    pub fn passes(&self, values: &dyn Fn(&str) -> Option<bool>) -> bool {
        for k in &self.requires {
            if values(k) != Some(true) {
                return false;
            }
        }
        for k in &self.excludes {
            if values(k) == Some(true) {
                return false;
            }
        }
        true
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Job {
    pub id: String,
    pub name: String,
    pub trigger: Trigger,
    pub action: String, // agent | macro | script reference
    pub guard: Guard,
    pub retry_max: u32,
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct JobRun {
    pub job_id: String,
    pub started_at: DateTime<Utc>,
    pub finished_at: Option<DateTime<Utc>>,
    pub success: bool,
    pub detail: String,
}

/// A deterministic tick scheduler. `evaluate(now, state)` returns jobs that
/// should fire at this instant.
#[derive(Debug, Clone, Default)]
pub struct Scheduler {
    pub jobs: Vec<Job>,
    pub history: Vec<JobRun>,
    pub last_eval: Option<DateTime<Utc>>,
    pub interval_state: std::collections::HashMap<String, DateTime<Utc>>,
}

impl Scheduler {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn upsert(&mut self, job: Job) {
        if let Some(existing) = self.jobs.iter_mut().find(|j| j.id == job.id) {
            *existing = job;
        } else {
            self.jobs.push(job);
        }
    }

    /// Which enabled jobs should run at `now`, given blackboard state.
    pub fn due(&mut self, now: DateTime<Utc>, state: &dyn Fn(&str) -> Option<bool>) -> Vec<String> {
        let mut out = Vec::new();
        let prev = self.last_eval.unwrap_or(now - chrono::Duration::minutes(1));
        self.last_eval = Some(now);

        for job in self.jobs.iter().filter(|j| j.enabled) {
            if !job.guard.passes(state) {
                continue;
            }
            let due = match &job.trigger {
                Trigger::Manual => false,
                Trigger::Cron(expr) => {
                    let c = crate::cron::parse_cron(expr).ok();
                    // fire at most once per minute window
                    c.map(|c| c.matches(&now))
                        .unwrap_or(false)
                        && (now - prev) >= chrono::Duration::seconds(30)
                }
                Trigger::Interval(d) => {
                    let last = self
                        .interval_state
                        .get(&job.id)
                        .copied()
                        .unwrap_or_else(|| now - chrono::Duration::seconds(d.0 as i64));
                    if (now - last).num_seconds() >= d.0 as i64 {
                        self.interval_state.insert(job.id.clone(), now);
                        true
                    } else {
                        false
                    }
                }
                Trigger::OneShot(t) => *t <= now,
                Trigger::Event(name) => state(name) == Some(true),
            };
            if due {
                out.push(job.id.clone());
                self.history.push(JobRun {
                    job_id: job.id.clone(),
                    started_at: now,
                    finished_at: None,
                    success: true,
                    detail: "scheduled".into(),
                });
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(k: &str) -> Option<bool> {
        match k {
            "game.online" => Some(true),
            "agent.lease" => Some(false),
            "hud.imprint.available" => Some(true),
            _ => None,
        }
    }

    fn job(id: &str, trigger: Trigger, enabled: bool) -> Job {
        Job {
            id: id.into(),
            name: id.into(),
            trigger,
            action: "imprinter".into(),
            guard: Guard::default(),
            retry_max: 2,
            enabled,
        }
    }

    #[test]
    fn interval_job_fires_periodically() {
        let mut s = Scheduler::new();
        s.upsert(job("tick", Trigger::Interval(DurationSec(10)), true));
        let t0 = Utc::now();
        let due1 = s.due(t0, &state);
        assert!(due1.contains(&"tick".into()));
        // immediately again: not yet
        let due2 = s.due(t0 + chrono::Duration::seconds(5), &state);
        assert!(due2.is_empty());
        let due3 = s.due(t0 + chrono::Duration::seconds(11), &state);
        assert!(due3.contains(&"tick".into()));
    }

    #[test]
    fn disabled_job_never_fires() {
        let mut s = Scheduler::new();
        s.upsert(job("off", Trigger::Interval(DurationSec(1)), false));
        let due = s.due(Utc::now(), &state);
        assert!(due.is_empty());
    }

    #[test]
    fn guard_blocks_when_excluded() {
        let mut s = Scheduler::new();
        let mut j = job("g", Trigger::Event("hud.imprint.available".into()), true);
        j.guard = Guard {
            requires: vec!["game.online".into()],
            excludes: vec!["agent.lease".into()],
        };
        s.upsert(j);
        let due = s.due(Utc::now(), &state);
        assert!(due.contains(&"g".into()));
    }

    #[test]
    fn event_trigger_needs_flag() {
        let mut s = Scheduler::new();
        s.upsert(job(
            "e",
            Trigger::Event("hud.imprint.available".into()),
            true,
        ));
        let no_flag = |k: &str| match k {
            "hud.imprint.available" => Some(false),
            _ => None,
        };
        let due = s.due(Utc::now(), &no_flag);
        assert!(due.is_empty());
    }
}
