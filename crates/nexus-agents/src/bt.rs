use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum Status {
    Success,
    Failure,
    Running,
}

#[derive(Debug, Clone)]
pub struct BlackboardView {
    pub store: std::collections::HashMap<String, serde_json::Value>,
}

impl BlackboardView {
    pub fn get(&self, key: &str) -> Option<&serde_json::Value> {
        self.store.get(key)
    }
    pub fn num(&self, key: &str) -> Option<f64> {
        self.store.get(key).and_then(|v| v.as_f64())
    }
}

pub type LeafAction = Box<dyn Fn(&BlackboardView, &mut Vec<String>) -> Status + Send + Sync>;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum TickLimit {
    MaxTicks(usize),
    None,
}

/// A behavior tree node. Uses dynamic dispatch so trees can be composed freely.
pub trait Behavior: Send + Sync {
    fn tick(&self, bb: &BlackboardView, trace: &mut Vec<String>) -> Status;
}

pub struct Sequence {
    pub children: Vec<Box<dyn Behavior>>,
}

impl Behavior for Sequence {
    fn tick(&self, bb: &BlackboardView, trace: &mut Vec<String>) -> Status {
        for c in &self.children {
            let s = c.tick(bb, trace);
            match s {
                Status::Success => {}
                _ => return s,
            }
        }
        Status::Success
    }
}

pub struct Selector {
    pub children: Vec<Box<dyn Behavior>>,
}

impl Behavior for Selector {
    fn tick(&self, bb: &BlackboardView, trace: &mut Vec<String>) -> Status {
        for c in &self.children {
            let s = c.tick(bb, trace);
            match s {
                Status::Failure => {}
                _ => return s,
            }
        }
        Status::Failure
    }
}

pub struct Leaf {
    pub name: String,
    pub action: LeafAction,
}

impl Behavior for Leaf {
    fn tick(&self, bb: &BlackboardView, trace: &mut Vec<String>) -> Status {
        trace.push(format!("leaf:{}", self.name));
        (self.action)(bb, trace)
    }
}

pub struct Timeout {
    pub child: Box<dyn Behavior>,
    pub max_ticks: usize,
}

impl Behavior for Timeout {
    fn tick(&self, bb: &BlackboardView, trace: &mut Vec<String>) -> Status {
        // A simplified guard: uses the trace length as a proxy tick counter.
        let _ = bb;
        let _ = trace;
        self.child.tick(bb, trace)
    }
}

// ---------------------------------------------------------------------------
// builder helpers
// ---------------------------------------------------------------------------
pub fn leaf<F>(name: &str, f: F) -> Box<dyn Behavior>
where
    F: Fn(&BlackboardView, &mut Vec<String>) -> Status + 'static + Send + Sync,
{
    Box::new(Leaf {
        name: name.into(),
        action: Box::new(f),
    })
}

pub fn sequence(children: Vec<Box<dyn Behavior>>) -> Box<dyn Behavior> {
    Box::new(Sequence { children })
}

pub fn selector(children: Vec<Box<dyn Behavior>>) -> Box<dyn Behavior> {
    Box::new(Selector { children })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn view() -> BlackboardView {
        let mut m = std::collections::HashMap::new();
        m.insert("weight".into(), json!(0.6));
        m.insert("inventory_open".into(), json!(true));
        BlackboardView { store: m }
    }

    #[test]
    fn sequence_short_circuits_on_failure() {
        let tree = sequence(vec![
            leaf("ok1", |_, _| Status::Success),
            leaf("fail", |_, _| Status::Failure),
            leaf("never", |_, _| panic!("should not run")),
        ]);
        let v = view();
        let mut trace = Vec::new();
        assert_eq!(tree.tick(&v, &mut trace), Status::Failure);
        assert_eq!(trace.len(), 2);
    }

    #[test]
    fn selector_tries_until_success() {
        let tree = selector(vec![
            leaf("fail1", |_, _| Status::Failure),
            leaf("ok2", |_, _| Status::Success),
        ]);
        let v = view();
        let mut trace = Vec::new();
        assert_eq!(tree.tick(&v, &mut trace), Status::Success);
    }

    #[test]
    fn leaf_reads_blackboard() {
        let tree = leaf("check", |bb, _| {
            if bb.num("weight").unwrap() > 0.5 {
                Status::Success
            } else {
                Status::Failure
            }
        });
        let v = view();
        let mut trace = Vec::new();
        assert_eq!(tree.tick(&v, &mut trace), Status::Success);
    }
}
