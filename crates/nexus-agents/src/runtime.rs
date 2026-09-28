use crate::bt::{Behavior, BlackboardView, Status};
use nexus_core::blackboard::Blackboard;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum AgentState {
    Idle,
    Planning,
    Acting,
    Verifying,
    Waiting,
    Blocked,
    Paused,
    Killed,
}

#[derive(Debug, Clone)]
pub struct AgentStatus {
    pub id: String,
    pub kind: String,
    pub state: AgentState,
    pub ticks: u64,
    pub failures: u64,
    pub last_trace: Vec<String>,
}

pub struct Agent {
    pub id: String,
    pub kind: String,
    pub tree: Box<dyn Behavior>,
    pub max_ticks: u64,
    pub max_failures: u64,
    pub state: AgentState,
    pub ticks: u64,
    pub failures: u64,
}

impl Agent {
    pub fn new(id: &str, kind: &str, tree: Box<dyn Behavior>) -> Self {
        Self {
            id: id.into(),
            kind: kind.into(),
            tree,
            max_ticks: 10_000,
            max_failures: 10,
            state: AgentState::Idle,
            ticks: 0,
            failures: 0,
        }
    }
}

/// Runtime that ticks agents against a blackboard, enforcing budgets.
pub struct AgentRuntime {
    pub agents: Vec<Agent>,
    pub blackboard: Blackboard,
}

impl Default for AgentRuntime {
    fn default() -> Self {
        Self {
            agents: Vec::new(),
            blackboard: Blackboard::new(),
        }
    }
}

impl AgentRuntime {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn spawn(&mut self, agent: Agent) {
        self.agents.push(agent);
    }

    pub fn status(&self) -> Vec<AgentStatus> {
        self.agents
            .iter()
            .map(|a| AgentStatus {
                id: a.id.clone(),
                kind: a.kind.clone(),
                state: a.state,
                ticks: a.ticks,
                failures: a.failures,
                last_trace: Vec::new(),
            })
            .collect()
    }

    /// Tick all non-paused agents once.
    pub fn tick_all(&mut self) {
        let view = self.blackboard_view();
        for agent in &mut self.agents {
            if agent.state == AgentState::Paused || agent.state == AgentState::Killed {
                continue;
            }
            agent.ticks += 1;
            if agent.ticks > agent.max_ticks {
                agent.state = AgentState::Blocked;
                continue;
            }
            let mut trace = Vec::new();
            let s = agent.tree.tick(&view, &mut trace);
            agent.state = match s {
                Status::Success => AgentState::Idle,
                Status::Running => AgentState::Acting,
                Status::Failure => {
                    agent.failures += 1;
                    AgentState::Blocked
                }
            };
        }
    }

    pub fn pause(&mut self, id: &str) {
        if let Some(a) = self.agents.iter_mut().find(|a| a.id == id) {
            a.state = AgentState::Paused;
        }
    }

    pub fn resume(&mut self, id: &str) {
        if let Some(a) = self.agents.iter_mut().find(|a| a.id == id) {
            a.state = AgentState::Acting;
        }
    }

    fn blackboard_view(&self) -> BlackboardView {
        let mut store = std::collections::HashMap::new();
        for (k, e) in &self.blackboard.store {
            store.insert(k.clone(), e.value.clone());
        }
        BlackboardView { store }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bt::{leaf, sequence, Status};
    use serde_json::json;

    #[test]
    fn agent_tick_executes_tree() {
        let tree = leaf("check_weight", |bb, _| {
            if bb.num("weight").unwrap_or(1.0) < 0.8 {
                Status::Success
            } else {
                Status::Failure
            }
        });
        let mut rt = AgentRuntime::new();
        rt.blackboard.set("weight", json!(0.5), "vision");
        rt.spawn(Agent::new("farmer", "Farmer", tree));
        rt.tick_all();
        let st = rt.status();
        assert_eq!(st[0].ticks, 1);
    }

    #[test]
    fn blocked_after_failure_budget() {
        let tree = leaf("always_fail", |_, _| Status::Failure);
        let mut rt = AgentRuntime::new();
        rt.spawn(Agent::new("a", "A", tree));
        for _ in 0..3 {
            rt.tick_all();
        }
        let st = rt.status();
        assert_eq!(st[0].state, AgentState::Blocked);
    }

    #[test]
    fn pause_prevents_ticks() {
        let tree = leaf("tick_me", |_, _| Status::Running);
        let mut rt = AgentRuntime::new();
        rt.spawn(Agent::new("a", "A", tree));
        rt.pause("a");
        rt.tick_all();
        let st = rt.status();
        assert_eq!(st[0].ticks, 0);
        assert_eq!(st[0].state, AgentState::Paused);
    }

    #[test]
    fn sequence_agent_succeeds() {
        let tree = sequence(vec![
            leaf("goto", |_, _| Status::Success),
            leaf("attack", |_, _| Status::Success),
            leaf("verify", |_, _| Status::Success),
        ]);
        let mut rt = AgentRuntime::new();
        rt.spawn(Agent::new("miner", "Miner", tree));
        rt.tick_all();
        let st = rt.status();
        assert_eq!(st[0].state, AgentState::Idle); // success -> idle
    }
}
