use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum ModelKind {
    Detector,
    Ocr,
    Planner,
    VisionLanguage,
    Embeddings,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Device {
    Cpu,
    Cuda,
    TensorRt,
    DirectMl,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum Provider {
    Local,
    Ollama,
    CloudOpenAi,
    CloudAnthropic,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ModelInfo {
    pub id: String,
    pub kind: ModelKind,
    pub format: String, // onnx | engine | gguf | api
    pub device: Device,
    pub provider: Provider,
    pub classes: Vec<String>,
}

#[derive(Debug, Clone, Error, PartialEq)]
pub enum ModelError {
    #[error("model not found: {0}")]
    NotFound(String),
    #[error("provider unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("no GPU backend; fallback to CPU required")]
    NoGpu,
}

/// The Model Registry (doc 11): declares models and resolves the best
/// provider/device with a fallback chain (GPU -> DirectML -> CPU).
pub struct ModelRegistry {
    pub models: HashMap<String, ModelInfo>,
    pub fallback_order: Vec<Device>,
}

impl Default for ModelRegistry {
    fn default() -> Self {
        Self {
            models: HashMap::new(),
            fallback_order: vec![Device::Cuda, Device::TensorRt, Device::DirectMl, Device::Cpu],
        }
    }
}

impl ModelRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, info: ModelInfo) {
        self.models.insert(info.id.clone(), info);
    }

    pub fn get(&self, id: &str) -> Option<&ModelInfo> {
        self.models.get(id)
    }

    /// Resolve the best device for a model given which GPU devices are
    /// actually available. Falls back down the chain.
    pub fn resolve_device(
        &self,
        id: &str,
        available: &[Device],
    ) -> Result<ModelInfo, ModelError> {
        let info = self.models.get(id).ok_or(ModelError::NotFound(id.into()))?;
        let mut resolved = info.clone();
        resolved.device = Device::Cpu;
        for d in &self.fallback_order {
            if available.contains(d) {
                resolved.device = *d;
                break;
            }
        }
        Ok(resolved)
    }

    /// GPU memory guard: refuse a GPU-resident model if free VRAM is below
    /// the budget.
    pub fn check_vram(&self, device: Device, free_mb: u64, budget_mb: u64) -> Result<(), ModelError> {
        if device == Device::Cpu {
            return Ok(());
        }
        if free_mb < budget_mb {
            Err(ModelError::NoGpu)
        } else {
            Ok(())
        }
    }

    pub fn list(&self) -> Vec<&ModelInfo> {
        self.models.values().collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn yolo() -> ModelInfo {
        ModelInfo {
            id: "yolo-ark-v3".into(),
            kind: ModelKind::Detector,
            format: "onnx".into(),
            device: Device::Cpu,
            provider: Provider::Local,
            classes: vec!["rex".into(), "metal_node".into()],
        }
    }

    #[test]
    fn register_and_get() {
        let mut r = ModelRegistry::new();
        r.register(yolo());
        assert_eq!(r.get("yolo-ark-v3").unwrap().kind, ModelKind::Detector);
        assert!(r.get("nope").is_none());
    }

    #[test]
    fn resolve_falls_back_to_cpu() {
        let mut r = ModelRegistry::new();
        r.register(yolo());
        let resolved = r.resolve_device("yolo-ark-v3", &[Device::DirectMl]).unwrap();
        assert_eq!(resolved.device, Device::DirectMl);
        let cpu = r.resolve_device("yolo-ark-v3", &[]).unwrap();
        assert_eq!(cpu.device, Device::Cpu);
    }

    #[test]
    fn resolve_unknown_model_errors() {
        let r = ModelRegistry::new();
        assert_eq!(
            r.resolve_device("ghost", &[Device::Cuda]),
            Err(ModelError::NotFound("ghost".into()))
        );
    }

    #[test]
    fn vram_guard_blocks_low_memory() {
        let r = ModelRegistry::new();
        assert_eq!(r.check_vram(Device::Cuda, 1024, 2048), Err(ModelError::NoGpu));
        assert!(r.check_vram(Device::Cuda, 4096, 2048).is_ok());
        assert!(r.check_vram(Device::Cpu, 0, 2048).is_ok());
    }
}
