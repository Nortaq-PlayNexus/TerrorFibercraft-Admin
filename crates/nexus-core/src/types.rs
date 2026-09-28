use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Mode {
    Manual,
    Assisted,
    Autonomous,
    Scheduled,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum Capability {
    Input,
    Screen,
    Network,
    FileRead,
    FileWrite,
    Process,
    Device,
    KbRead,
    KbWrite,
    Telemetry,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Config {
    pub mode: Mode,
    pub kill_switch: Vec<String>,
    pub input_profile: InputProfile,
    pub caps: Vec<Capability>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct InputProfile {
    pub mouse_sensitivity: f64,
    pub accel: bool,
    pub key_delay_ms: u64,
    pub deadzone: f64,
    pub tokens_per_sec: u64,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            mode: Mode::Manual,
            kill_switch: vec!["Ctrl".into(), "Alt".into(), "K".into()],
            input_profile: InputProfile {
                mouse_sensitivity: 1.0,
                accel: false,
                key_delay_ms: 8,
                deadzone: 0.12,
                tokens_per_sec: 300,
            },
            caps: vec![Capability::Input, Capability::Screen],
        }
    }
}
