use crate::package::PackageError;
use sha2::{Digest, Sha256};

/// Compute SHA-256 hex digest of a package's canonical manifest bytes.
pub fn hash_manifest(bytes: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(bytes);
    hex::encode(h.finalize())
}

/// A deterministic "signature": HMAC-style using a keyed SHA-256 of the content.
/// In production this is replaced by real Ed25519; the shape is identical so the
/// verification boundary is already in place.
pub fn sign(content: &[u8], key: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(key);
    h.update(b":");
    h.update(content);
    hex::encode(h.finalize())
}

pub fn verify_signature(content: &[u8], key: &[u8], expected: &str) -> Result<(), PackageError> {
    let actual = sign(content, key);
    if actual == expected {
        Ok(())
    } else {
        Err(PackageError::MissingSignature)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sign_and_verify_roundtrip() {
        let key = b"test-secret";
        let data = b"manifest-bytes";
        let sig = sign(data, key);
        assert!(verify_signature(data, key, &sig).is_ok());
    }

    #[test]
    fn wrong_key_fails() {
        let key = b"test-secret";
        let data = b"manifest-bytes";
        let sig = sign(data, key);
        assert!(verify_signature(data, b"other-key", &sig).is_err());
    }

    #[test]
    fn tampered_content_fails() {
        let key = b"test-secret";
        let sig = sign(b"original", key);
        assert!(verify_signature(b"tampered", key, &sig).is_err());
    }

    #[test]
    fn hash_is_stable() {
        let h1 = hash_manifest(b"abc");
        let h2 = hash_manifest(b"abc");
        assert_eq!(h1, h2);
        assert_eq!(h1.len(), 64);
    }
}
