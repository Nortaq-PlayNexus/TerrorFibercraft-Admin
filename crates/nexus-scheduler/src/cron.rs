use chrono::{Datelike, Timelike};
use thiserror::Error;

#[derive(Debug, Clone, PartialEq)]
pub struct CronExpr {
    /// minute-of-hour 0-59, '*' or range
    pub minute: Field,
    /// hour 0-23
    pub hour: Field,
    /// day-of-month 1-31
    pub dom: Field,
    /// month 1-12
    pub month: Field,
    /// day-of-week 0-6 (0=Sunday)
    pub dow: Field,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Field {
    Any,
    Set(std::collections::BTreeSet<u32>),
}

#[derive(Debug, Clone, Error, PartialEq)]
pub enum CronError {
    #[error("invalid cron field '{0}'")]
    BadField(String),
    #[error("expected 5 fields, got {0}")]
    WrongArity(usize),
}

impl Field {
    pub fn matches(&self, v: u32) -> bool {
        match self {
            Field::Any => true,
            Field::Set(s) => s.contains(&v),
        }
    }
}

fn parse_field(s: &str, max: u32) -> Result<Field, CronError> {
    if s == "*" {
        return Ok(Field::Any);
    }
    let mut set = std::collections::BTreeSet::new();
    for part in s.split(',') {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }
        if part.contains('-') {
            let (a, b) = part.split_once('-').ok_or(CronError::BadField(part.into()))?;
            let a: u32 = a.parse().map_err(|_| CronError::BadField(part.into()))?;
            let b: u32 = b.parse().map_err(|_| CronError::BadField(part.into()))?;
            if a > b || b > max {
                return Err(CronError::BadField(part.into()));
            }
            for v in a..=b {
                set.insert(v);
            }
        } else {
            let v: u32 = part.parse().map_err(|_| CronError::BadField(part.into()))?;
            if v > max {
                return Err(CronError::BadField(part.into()));
            }
            set.insert(v);
        }
    }
    Ok(Field::Set(set))
}

/// Parse a standard 5-field cron expression.
pub fn parse_cron(s: &str) -> Result<CronExpr, CronError> {
    let parts: Vec<&str> = s.split_whitespace().collect();
    if parts.len() != 5 {
        return Err(CronError::WrongArity(parts.len()));
    }
    Ok(CronExpr {
        minute: parse_field(parts[0], 59)?,
        hour: parse_field(parts[1], 23)?,
        dom: parse_field(parts[2], 31)?,
        month: parse_field(parts[3], 12)?,
        dow: parse_field(parts[4], 6)?,
    })
}

impl CronExpr {
    /// Does the cron expression match the given minute of this datetime?
    pub fn matches(&self, dt: &chrono::DateTime<chrono::Utc>) -> bool {
        let m = dt.minute();
        let h = dt.hour();
        let dom = dt.day();
        let month = dt.month();
        let dow = dt.weekday().num_days_from_sunday();
        self.minute.matches(m)
            && self.hour.matches(h)
            && self.dom.matches(dom)
            && self.month.matches(month)
            && self.dow.matches(dow)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{TimeZone, Utc};

    fn dt(s: &str) -> chrono::DateTime<chrono::Utc> {
        Utc.datetime_from_str(s, "%Y-%m-%d %H:%M:%S").unwrap()
    }

    #[test]
    fn every_minute_matches_all() {
        let c = parse_cron("* * * * *").unwrap();
        assert!(c.matches(&dt("2026-08-02 12:00:00")));
        assert!(c.matches(&dt("2026-08-02 23:59:00")));
    }

    #[test]
    fn hourly_at_quarter() {
        let c = parse_cron("15 * * * *").unwrap();
        assert!(c.matches(&dt("2026-08-02 10:15:00")));
        assert!(!c.matches(&dt("2026-08-02 10:16:00")));
    }

    #[test]
    fn daily_at_night() {
        let c = parse_cron("0 22 * * *").unwrap();
        assert!(c.matches(&dt("2026-08-02 22:00:00")));
        assert!(!c.matches(&dt("2026-08-02 21:00:00")));
    }

    #[test]
    fn range_and_list() {
        let c = parse_cron("0 9-11 * * 1-5").unwrap();
        assert!(c.matches(&dt("2026-08-03 09:00:00"))); // Monday
        assert!(!c.matches(&dt("2026-08-02 09:00:00"))); // Sunday
    }

    #[test]
    fn invalid_arity() {
        assert_eq!(parse_cron("* * *"), Err(CronError::WrongArity(3)));
    }

    #[test]
    fn out_of_range_rejected() {
        assert!(parse_cron("0 25 * * *").is_err());
    }
}
