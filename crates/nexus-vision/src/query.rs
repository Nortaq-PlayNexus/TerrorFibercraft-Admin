use crate::pipeline::{DetectedObject, ScreenState};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct VisionQuery {
    pub op: Op,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Op {
    Any(Vec<Predicate>),
    All(Vec<Predicate>),
    None(Vec<Predicate>),
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Predicate {
    pub class: String,
    pub min_conf: f64,
    pub max_stale_ms: u64,
}

#[derive(Debug, Clone, Error, PartialEq)]
pub enum QueryError {
    #[error("no matching object for {class}")]
    NoMatch { class: String },
}

impl VisionQuery {
    /// Evaluate against a screen state snapshot. Returns matched objects.
    pub fn evaluate<'a>(
        &self,
        state: &'a ScreenState,
    ) -> Result<Vec<&'a DetectedObject>, QueryError> {
        let matches = |p: &Predicate| -> Vec<&'a DetectedObject> {
            state
                .objects
                .iter()
                .filter(|o| {
                    o.class == p.class
                        && o.confidence >= p.min_conf
                        && state.captured_at_ms.saturating_sub(o.last_seen_ms) <= p.max_stale_ms
                })
                .collect()
        };

        match &self.op {
            Op::Any(preds) => {
                for p in preds {
                    let m = matches(p);
                    if !m.is_empty() {
                        return Ok(m);
                    }
                }
                Err(QueryError::NoMatch {
                    class: preds.first().map(|p| p.class.clone()).unwrap_or_default(),
                })
            }
            Op::All(preds) => {
                let mut out = Vec::new();
                for p in preds {
                    let m = matches(p);
                    if m.is_empty() {
                        return Err(QueryError::NoMatch {
                            class: p.class.clone(),
                        });
                    }
                    out.extend(m);
                }
                Ok(out)
            }
            Op::None(preds) => {
                for p in preds {
                    if !matches(p).is_empty() {
                        return Err(QueryError::NoMatch {
                            class: p.class.clone(),
                        });
                    }
                }
                Ok(vec![])
            }
        }
    }
}

impl VisionQuery {
    pub fn any(class: &str) -> Self {
        Self {
            op: Op::Any(vec![Predicate {
                class: class.into(),
                min_conf: 0.5,
                max_stale_ms: 2000,
            }]),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pipeline::DetectedObject;

    fn obj(class: &str, conf: f64, seen_ago_ms: u64, now: u64) -> DetectedObject {
        DetectedObject {
            track_id: 1,
            class: class.into(),
            confidence: conf,
            bbox: [0, 0, 10, 10],
            world: None,
            last_seen_ms: now.saturating_sub(seen_ago_ms),
        }
    }

    fn state(objects: Vec<DetectedObject>) -> ScreenState {
        let mut s = ScreenState {
            captured_at_ms: 1000,
            fps: 30.0,
            ..Default::default()
        };
        s.objects = objects;
        s
    }

    #[test]
    fn any_matches_when_present() {
        let s = state(vec![obj("metal_node", 0.9, 100, 1000)]);
        assert!(VisionQuery::any("metal_node").evaluate(&s).is_ok());
    }

    #[test]
    fn any_fails_when_absent() {
        let s = state(vec![]);
        assert!(VisionQuery::any("rex").evaluate(&s).is_err());
    }

    #[test]
    fn stale_objects_excluded() {
        // object last seen at t=0, snapshot captured at t=9000 (9s stale)
        let mut s = state(vec![obj("rex", 0.9, 9000, 9000)]);
        s.captured_at_ms = 9000;
        assert!(VisionQuery::any("rex").evaluate(&s).is_err());
    }

    #[test]
    fn low_confidence_excluded() {
        let s = state(vec![obj("rex", 0.3, 100, 1000)]);
        assert!(VisionQuery::any("rex").evaluate(&s).is_err());
    }

    #[test]
    fn none_passes_when_clear() {
        let s = state(vec![obj("metal_node", 0.9, 100, 1000)]);
        let q = VisionQuery {
            op: Op::None(vec![Predicate {
                class: "rex".into(),
                min_conf: 0.5,
                max_stale_ms: 2000,
            }]),
        };
        assert!(q.evaluate(&s).is_ok());
    }
}
