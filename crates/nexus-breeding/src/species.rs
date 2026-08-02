use chrono::{Duration, Utc};
use serde::{Deserialize, Serialize};

/// Species maturation/imprint characteristics (subset of doc 07 tables).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MaturationProfile {
    pub species: String,
    /// total maturation time
    pub maturation_hours: f64,
    /// seconds between imprint requirements
    pub imprint_interval_secs: f64,
    /// required imprint % per requirement
    pub imprint_per_req: f64,
}

impl MaturationProfile {
    /// Remaining time until maturation given current percent (0..1).
    pub fn eta(&self, percent: f64) -> Duration {
        let remaining = (1.0 - percent) * self.maturation_hours * 3600.0;
        Duration::seconds(remaining.max(0.0) as i64)
    }
}

/// Time until the next imprint is ready, given maturation percent and
/// cumulative imprint so far.
pub fn imprint_ready(profile: &MaturationProfile, percent: f64) -> Duration {
    // Number of intervals that have elapsed; the next requirement is at the
    // boundary of the next interval.
    let elapsed_frac = percent * profile.maturation_hours * 3600.0 / profile.imprint_interval_secs;
    let next = (elapsed_frac.floor() + 1.0) * profile.imprint_interval_secs;
    let now_elapsed = percent * profile.maturation_hours * 3600.0;
    Duration::seconds((next - now_elapsed).max(0.0) as i64)
}

/// Max imprint a baby can reach before the maturation is done, assuming the
/// user can respond to every requirement.
pub fn max_imprint(profile: &MaturationProfile) -> f64 {
    let total_secs = profile.maturation_hours * 3600.0;
    let intervals = (total_secs / profile.imprint_interval_secs).ceil();
    intervals * profile.imprint_per_req
}

pub fn maturation_eta(profile: &MaturationProfile, percent: f64) -> Duration {
    profile.eta(percent)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rex() -> MaturationProfile {
        MaturationProfile {
            species: "Rex".into(),
            maturation_hours: 100.0,
            imprint_interval_secs: 4.0 * 3600.0, // every 4 hours
            imprint_per_req: 0.125,
        }
    }

    #[test]
    fn eta_at_zero_is_full() {
        let p = rex();
        assert_eq!(p.eta(0.0).num_seconds(), 360_000);
    }

    #[test]
    fn eta_at_half_is_half() {
        let p = rex();
        assert_eq!(p.eta(0.5).num_seconds(), 180_000);
    }

    #[test]
    fn imprint_ready_positive_before_boundary() {
        let p = rex();
        // at 5% maturation, ~5 hours in; next imprint at 4h boundary already passed,
        // so next is at 8h boundary
        let t = imprint_ready(&p, 0.05);
        assert!(t.num_seconds() > 0);
    }

    #[test]
    fn max_imprint_rex_reasonable() {
        let p = rex();
        let m = max_imprint(&p);
        assert!(m > 1.0, "25 intervals * 0.125 = 3.125; got {m}");
    }

    #[test]
    fn full_maturation_eta_zero() {
        let p = rex();
        assert_eq!(maturation_eta(&p, 1.0).num_seconds(), 0);
    }
}
