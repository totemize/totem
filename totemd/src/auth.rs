//! Clock-independent, nonce-bound NIP-98 owner authorization.

use std::{
    collections::HashMap,
    sync::Mutex,
    time::{Duration, Instant},
};

use base64::{engine::general_purpose::STANDARD, Engine};
use bitcoin_hashes::sha256;
use nostr::prelude::{Event, Kind, PublicKey};

use crate::challenge;

const NONCE_LIFETIME: Duration = Duration::from_secs(300);
const MAX_NONCES: usize = 128;
const MAX_BODY: usize = 16 * 1024;
const MAX_AUTH_HEADER: usize = 96 * 1024;

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ChallengeRequest {
    pub path: String,
    pub method: String,
    pub body: String,
}

#[derive(serde::Serialize)]
pub struct ChallengeResponse {
    pub nonce: String,
    pub url: String,
    pub method: String,
    pub payload: String,
}

struct Record {
    issued: Instant,
    url: String,
    method: String,
    payload: String,
}

#[derive(Default)]
pub struct Nonces(Mutex<HashMap<String, Record>>);

impl Nonces {
    pub fn issue(
        &self,
        base_url: &str,
        request: ChallengeRequest,
    ) -> Result<ChallengeResponse, String> {
        validate_target(&request.path, &request.method)?;
        if request.body.len() > MAX_BODY {
            return Err("request body is too large".into());
        }
        let nonce = challenge::nonce()?;
        let url = format!("{base_url}{}", request.path);
        let payload = sha256::Hash::hash(request.body.as_bytes()).to_string();
        let response = ChallengeResponse {
            nonce: nonce.clone(),
            url: url.clone(),
            method: request.method.clone(),
            payload: payload.clone(),
        };
        let now = Instant::now();
        let mut records = self.0.lock().unwrap();
        records.retain(|_, record| now.duration_since(record.issued) <= NONCE_LIFETIME);
        if records.len() >= MAX_NONCES {
            let oldest = records
                .iter()
                .min_by_key(|(_, record)| record.issued)
                .map(|(nonce, _)| nonce.clone());
            if let Some(oldest) = oldest {
                records.remove(&oldest);
            }
        }
        records.insert(
            nonce,
            Record {
                issued: now,
                url,
                method: request.method,
                payload,
            },
        );
        Ok(response)
    }

    pub fn verify(
        &self,
        authorization: &str,
        url: &str,
        method: &str,
        body: &[u8],
    ) -> Result<PublicKey, String> {
        if body.len() > MAX_BODY || authorization.len() > MAX_AUTH_HEADER {
            return Err("authorization request is too large".into());
        }
        let encoded = authorization
            .strip_prefix("Nostr ")
            .filter(|value| !value.is_empty())
            .ok_or_else(|| "malformed Nostr authorization".to_string())?;
        let decoded = STANDARD
            .decode(encoded)
            .map_err(|e| format!("decode Nostr authorization: {e}"))?;
        let event: Event =
            serde_json::from_slice(&decoded).map_err(|e| format!("authorization event: {e}"))?;
        event
            .verify()
            .map_err(|e| format!("authorization signature: {e}"))?;
        if event.kind != Kind::HttpAuth || !event.content.is_empty() || event.tags.len() != 4 {
            return Err("authorization event shape is invalid".into());
        }
        let nonce = challenge::exact_tag(&event, "nonce")
            .ok_or_else(|| "authorization nonce is missing".to_string())?;
        let record = self
            .0
            .lock()
            .unwrap()
            .remove(nonce)
            .ok_or_else(|| "authorization nonce is unknown or already used".to_string())?;
        if record.issued.elapsed() > NONCE_LIFETIME {
            return Err("authorization nonce expired".into());
        }
        let payload = sha256::Hash::hash(body).to_string();
        if record.url != url
            || record.method != method
            || record.payload != payload
            || challenge::exact_tag(&event, "u") != Some(url)
            || challenge::exact_tag(&event, "method") != Some(method)
            || challenge::exact_tag(&event, "payload") != Some(payload.as_str())
        {
            return Err("authorization does not match request".into());
        }
        Ok(event.pubkey)
    }
}

fn validate_target(path: &str, method: &str) -> Result<(), String> {
    match (method, path) {
        ("POST", "/api/owner/claim")
        | ("PUT", "/api/metadata")
        | ("PUT", "/api/config")
        | ("GET", "/api/owner/events") => Ok(()),
        _ => Err("unsupported authorization target".into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nostr::{
        event::FinalizeEvent,
        prelude::{EventBuilder, Keys, Tag, Timestamp},
    };

    fn authorization(keys: &Keys, challenge: &ChallengeResponse) -> String {
        let tags = [
            Tag::parse(["nonce", challenge.nonce.as_str()]).unwrap(),
            Tag::parse(["u", challenge.url.as_str()]).unwrap(),
            Tag::parse(["method", challenge.method.as_str()]).unwrap(),
            Tag::parse(["payload", challenge.payload.as_str()]).unwrap(),
        ];
        let event = EventBuilder::new(Kind::HttpAuth, "")
            .tags(tags)
            .custom_created_at(Timestamp::from_secs(1))
            .finalize(keys)
            .unwrap();
        format!("Nostr {}", STANDARD.encode(event.as_json()))
    }

    #[test]
    fn authorization_is_bound_and_single_use_without_wall_clock() {
        let nonces = Nonces::default();
        let body = r#"{"sync":false,"befriend":"ask"}"#;
        let challenge = nonces
            .issue(
                "http://totem.local:8080",
                ChallengeRequest {
                    path: "/api/config".into(),
                    method: "PUT".into(),
                    body: body.into(),
                },
            )
            .unwrap();
        let keys = Keys::parse(&format!("{:064x}", 3)).unwrap();
        let auth = authorization(&keys, &challenge);
        assert_eq!(
            nonces
                .verify(&auth, &challenge.url, "PUT", body.as_bytes())
                .unwrap(),
            keys.public_key()
        );
        assert!(nonces
            .verify(&auth, &challenge.url, "PUT", body.as_bytes())
            .is_err());
    }

    #[test]
    fn body_target_and_shape_are_strict() {
        let nonces = Nonces::default();
        assert!(nonces
            .issue(
                "http://totem",
                ChallengeRequest {
                    path: "/api/nope".into(),
                    method: "DELETE".into(),
                    body: String::new(),
                },
            )
            .is_err());

        assert!(nonces
            .issue(
                "http://totem",
                ChallengeRequest {
                    path: "/api/owner/events".into(),
                    method: "GET".into(),
                    body: String::new(),
                },
            )
            .is_ok());

        let challenge = nonces
            .issue(
                "http://totem",
                ChallengeRequest {
                    path: "/api/owner/claim".into(),
                    method: "POST".into(),
                    body: "{}".into(),
                },
            )
            .unwrap();
        let keys = Keys::parse(&format!("{:064x}", 4)).unwrap();
        let auth = authorization(&keys, &challenge);
        assert!(nonces
            .verify(&auth, &challenge.url, "POST", b"{\"changed\":true}")
            .is_err());
    }
}
