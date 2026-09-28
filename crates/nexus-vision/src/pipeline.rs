use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct PlayerState {
    pub hp: f64,
    pub weight: f64,
    pub stamina: f64,
    pub inventory_open: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct HudState {
    pub taming_percent: Option<f64>,
    pub taming_effectiveness: Option<f64>,
    pub maturation_percent: Option<f64>,
    pub imprint_percent: Option<f64>,
    pub coords: Option<(f64, f64)>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct DetectedObject {
    pub track_id: u64,
    pub class: String,
    pub confidence: f64,
    pub bbox: [u32; 4],
    pub world: Option<(f64, f64)>,
    pub last_seen_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct ScreenState {
    pub captured_at_ms: u64,
    pub fps: f64,
    pub player: PlayerState,
    pub hud: HudState,
    pub objects: Vec<DetectedObject>,
    pub warnings: Vec<String>,
}

/// Temporal fusion: matches new detections to existing tracks by IoU,
/// producing stable track ids across frames.
#[derive(Debug, Clone)]
pub struct TemporalTracker {
    next_id: u64,
    pub tracks: Vec<DetectedObject>,
    pub iou_threshold: f64,
    pub max_age_ms: u64,
    pub now: u64,
}

impl Default for TemporalTracker {
    fn default() -> Self {
        Self {
            next_id: 1,
            tracks: Vec::new(),
            iou_threshold: 0.3,
            max_age_ms: 5000,
            now: 0,
        }
    }
}

impl TemporalTracker {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn iou(a: &[u32; 4], b: &[u32; 4]) -> f64 {
        let x1 = a[0].max(b[0]) as i64;
        let y1 = a[1].max(b[1]) as i64;
        let x2 = (a[0] + a[2]).min(b[0] + b[2]) as i64;
        let y2 = (a[1] + a[3]).min(b[1] + b[3]) as i64;
        let inter = ((x2 - x1).max(0) * (y2 - y1).max(0)) as f64;
        let area_a = (a[2] * a[3]) as f64;
        let area_b = (b[2] * b[3]) as f64;
        let union = area_a + area_b - inter;
        if union <= 0.0 {
            0.0
        } else {
            inter / union
        }
    }

    /// Advance tracker with a new frame's detections (class + bbox).
    pub fn update(&mut self, detections: &[(String, f64, [u32; 4])], now_ms: u64) {
        self.now = now_ms;
        // age out old tracks
        self.tracks.retain(|t| now_ms.saturating_sub(t.last_seen_ms) <= self.max_age_ms);

        for (class, conf, bbox) in detections {
            let mut best: Option<(usize, f64)> = None;
            for (i, t) in self.tracks.iter().enumerate() {
                if &t.class != class {
                    continue;
                }
                let iou = Self::iou(&t.bbox, bbox);
                if iou >= self.iou_threshold {
                    match best {
                        Some((_, biou)) if biou >= iou => {}
                        _ => best = Some((i, iou)),
                    }
                }
            }
            match best {
                Some((i, _)) => {
                    let t = &mut self.tracks[i];
                    t.bbox = *bbox;
                    t.confidence = *conf;
                    t.last_seen_ms = now_ms;
                }
                None => {
                    self.tracks.push(DetectedObject {
                        track_id: self.next_id,
                        class: class.clone(),
                        confidence: *conf,
                        bbox: *bbox,
                        world: None,
                        last_seen_ms: now_ms,
                    });
                    self.next_id += 1;
                }
            }
        }
    }

    pub fn snapshot(&self) -> Vec<DetectedObject> {
        self.tracks.clone()
    }

    /// Objects of a class still fresh.
    pub fn fresh(&self, class: &str) -> Vec<&DetectedObject> {
        self.tracks
            .iter()
            .filter(|t| t.class == class && self.now.saturating_sub(t.last_seen_ms) <= 2000)
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn iou_calculation() {
        let a = [0, 0, 100, 100];
        let b = [50, 50, 100, 100]; // overlap 50x50
        // bboxes are [x, y, w, h]; union = 10000+10000-2500
        assert!((TemporalTracker::iou(&a, &b) - (2500.0 / 17500.0)).abs() < 1e-6);
        let c = [200, 200, 10, 10];
        assert_eq!(TemporalTracker::iou(&a, &c), 0.0);
    }

    #[test]
    fn stable_track_ids_across_frames() {
        let mut t = TemporalTracker::new();
        t.update(&[("rex".into(), 0.9, [0, 0, 100, 100])], 1000);
        t.update(&[("rex".into(), 0.9, [5, 5, 100, 100])], 1100);
        let snap = t.snapshot();
        assert_eq!(snap.len(), 1);
        assert_eq!(snap[0].track_id, 1);
    }

    #[test]
    fn new_class_gets_new_track() {
        let mut t = TemporalTracker::new();
        t.update(&[("rex".into(), 0.9, [0, 0, 100, 100])], 1000);
        t.update(&[("metal_node".into(), 0.8, [300, 300, 20, 20])], 1100);
        assert_eq!(t.snapshot().len(), 2);
    }

    #[test]
    fn stale_tracks_age_out() {
        let mut t = TemporalTracker::new();
        t.update(&[("rex".into(), 0.9, [0, 0, 100, 100])], 1000);
        t.update(&[], 9000);
        assert!(t.snapshot().is_empty());
    }
}
