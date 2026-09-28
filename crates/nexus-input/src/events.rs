use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum KeyState {
    Down,
    Up,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum ProducerKind {
    User,
    AgentEmergency,
    Scheduler,
    Macro,
    Script,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct ProducerId(pub ProducerKind, pub String);

impl ProducerId {
    pub fn new(kind: ProducerKind, id: impl Into<String>) -> Self {
        Self(kind, id.into())
    }
    pub fn priority(&self) -> u8 {
        match self.0 {
            ProducerKind::User => 0,
            ProducerKind::AgentEmergency => 1,
            ProducerKind::Scheduler => 2,
            ProducerKind::Macro => 3,
            ProducerKind::Script => 4,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct InputEvent {
    pub id: u64,
    pub ts: f64,
    pub kind: EventKind,
    pub device: Device,
    pub producer: ProducerId,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum Device {
    Physical,
    Virtual,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum EventKind {
    KeyDown { key: String },
    KeyUp { key: String },
    MouseMove { dx: i32, dy: i32 },
    MouseDown { button: String },
    MouseUp { button: String },
    MouseWheel { delta: i32 },
    Axis { axis: String, value: f64 },
    Button { button: String, state: KeyState },
}

#[derive(Debug, Clone, Error, PartialEq)]
pub enum InputError {
    #[error("producer {0} exceeded token budget")]
    RateLimited(String),
    #[error("kill switch engaged")]
    KillSwitch,
    #[error("event dropped: queue full")]
    QueueFull,
    #[error("arbitration denied for producer {0} (mode not autonomous)")]
    Denied(String),
}
