use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum ReviewTier {
    Local,
    Community,
    Curated,
    Official,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
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
pub struct Manifest {
    pub id: String,
    pub name: String,
    pub version: String,
    pub author: String,
    pub capabilities: Vec<Capability>,
    pub tier: ReviewTier,
    pub lang: Option<String>,
    pub deps: Vec<Dep>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Dep {
    pub id: String,
    pub version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Package {
    pub manifest: Manifest,
    pub hash: String,
    pub signature: Option<String>,
}

#[derive(Debug, Clone, Error, PartialEq)]
pub enum PackageError {
    #[error("capability {0:?} not allowed for tier {1:?}")]
    CapabilityForbidden(Capability, ReviewTier),
    #[error("duplicate dependency: {0}")]
    DuplicateDep(String),
    #[error("invalid version string: {0}")]
    BadVersion(String),
    #[error("signature missing")]
    MissingSignature,
}

impl Package {
    /// Validate package sanity: version format, no duplicate deps,
    /// and tier-appropriate capabilities.
    pub fn validate(&self) -> Result<(), PackageError> {
        validate_version(&self.manifest.version)?;
        let mut seen = std::collections::HashSet::new();
        for d in &self.manifest.deps {
            validate_version(&d.version)?;
            if !seen.insert(&d.id) {
                return Err(PackageError::DuplicateDep(d.id.clone()));
            }
        }
        let high_risk = [Capability::Network, Capability::FileWrite, Capability::Process];
        for cap in &self.manifest.capabilities {
            if high_risk.contains(cap)
                && matches!(self.manifest.tier, ReviewTier::Community)
            {
                return Err(PackageError::CapabilityForbidden(cap.clone(), self.manifest.tier));
            }
        }
        Ok(())
    }
}

fn validate_version(v: &str) -> Result<(), PackageError> {
    let parts: Vec<&str> = v.split('.').collect();
    if parts.len() != 3 {
        return Err(PackageError::BadVersion(v.into()));
    }
    for p in parts {
        if p.is_empty() || !p.chars().all(|c| c.is_ascii_digit()) {
            return Err(PackageError::BadVersion(v.into()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pkg(tier: ReviewTier, caps: Vec<Capability>) -> Package {
        Package {
            manifest: Manifest {
                id: "com.x.y".into(),
                name: "y".into(),
                version: "1.2.0".into(),
                author: "a".into(),
                capabilities: caps,
                tier,
                lang: Some("1".into()),
                deps: vec![],
            },
            hash: "abc".into(),
            signature: None,
        }
    }

    #[test]
    fn valid_official_package() {
        assert!(pkg(ReviewTier::Official, vec![Capability::Input])
            .validate()
            .is_ok());
    }

    #[test]
    fn community_network_forbidden() {
        assert_eq!(
            pkg(ReviewTier::Community, vec![Capability::Network]).validate(),
            Err(PackageError::CapabilityForbidden(
                Capability::Network,
                ReviewTier::Community
            ))
        );
    }

    #[test]
    fn local_can_have_filewrite() {
        assert!(pkg(ReviewTier::Local, vec![Capability::FileWrite])
            .validate()
            .is_ok());
    }

    #[test]
    fn bad_version_rejected() {
        let mut p = pkg(ReviewTier::Official, vec![]);
        p.manifest.version = "1.2".into();
        assert!(p.validate().is_err());
    }

    #[test]
    fn duplicate_dep_rejected() {
        let mut p = pkg(ReviewTier::Official, vec![]);
        p.manifest.deps = vec![
            Dep { id: "a".into(), version: "1.0.0".into() },
            Dep { id: "a".into(), version: "2.0.0".into() },
        ];
        assert_eq!(
            p.validate(),
            Err(PackageError::DuplicateDep("a".into()))
        );
    }
}
