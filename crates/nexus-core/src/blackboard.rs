use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct Blackboard {
    pub store: HashMap<String, Entry>,
}

#[derive(Debug, Clone)]
pub struct Entry {
    pub value: serde_json::Value,
    pub ts: i64,
    pub writer: String,
}

impl Blackboard {
    pub fn new() -> Self {
        Self {
            store: HashMap::new(),
        }
    }

    pub fn set(&mut self, key: &str, value: serde_json::Value, writer: &str) {
        self.store.insert(
            key.to_string(),
            Entry {
                value,
                ts: chrono::Utc::now().timestamp_millis(),
                writer: writer.to_string(),
            },
        );
    }

    pub fn get(&self, key: &str) -> Option<&serde_json::Value> {
        self.store.get(key).map(|e| &e.value)
    }

    pub fn get_stale_ms(&self, key: &str, now: i64) -> Option<i64> {
        self.store.get(key).map(|e| now - e.ts)
    }
}

impl Default for Blackboard {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn set_get_roundtrip() {
        let mut bb = Blackboard::new();
        bb.set("inv.metal", json!(1200), "vision");
        assert_eq!(bb.get("inv.metal"), Some(&json!(1200)));
    }

    #[test]
    fn staleness_tracking() {
        let mut bb = Blackboard::new();
        let now = chrono::Utc::now().timestamp_millis();
        bb.set("world.night", json!(false), "vision");
        let stale = bb.get_stale_ms("world.night", now + 5000).unwrap();
        assert!(stale >= 4000 && stale <= 6000, "stale={stale}");
    }
}
