//! Signed totem challenge: public responder + candidate-side verifier.

use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};

use axum::{
    extract::{Query, State},
    http::{header, uri::Authority, HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use nostr::{
    event::FinalizeEvent,
    nips::nip19::FromBech32,
    prelude::{Event, EventBuilder, Keys, Kind, PublicKey, Tag},
};
use serde::{Deserialize, Serialize};
use zeroize::Zeroizing;

use crate::{http, state::AppState, sync};

const PATH: &str = "/totem/challenge";
const WEB_PORT: u16 = 8080;
const SIGN_WINDOW: Duration = Duration::from_secs(1);
const MAX_SIGNATURES_PER_WINDOW: u8 = 8;

#[derive(Debug)]
enum SignError {
    BadRequest(&'static str),
    RateLimited,
    Internal(String),
}

pub struct Signer {
    keys: Keys,
    // ponytail: global burst bucket; add source-IP buckets only if guest
    // traffic measurably starves legitimate peers.
    rate: Mutex<(Instant, u8)>,
}

impl Signer {
    pub fn load(path: &Path) -> Result<Self, String> {
        let secret = Zeroizing::new(
            fs::read_to_string(path).map_err(|e| format!("read {}: {e}", path.display()))?,
        );
        let keys = Keys::parse(secret.trim()).map_err(|e| format!("parse device key: {e}"))?;
        Ok(Self::new(keys))
    }

    fn new(keys: Keys) -> Self {
        Self {
            keys,
            rate: Mutex::new((Instant::now(), 0)),
        }
    }

    pub fn public_key(&self) -> PublicKey {
        self.keys.public_key()
    }

    fn sign(&self, nonce: &str, url: &str) -> Result<Event, SignError> {
        validate_nonce(nonce).map_err(SignError::BadRequest)?;
        let now = Instant::now();
        let mut rate = self.rate.lock().unwrap();
        if now.duration_since(rate.0) >= SIGN_WINDOW {
            *rate = (now, 0);
        }
        if rate.1 >= MAX_SIGNATURES_PER_WINDOW {
            return Err(SignError::RateLimited);
        }
        rate.1 += 1;
        drop(rate);
        signed_event(&self.keys, nonce, url).map_err(SignError::Internal)
    }
}

pub fn key_path() -> PathBuf {
    if let Some(path) = std::env::var_os("TOTEMD_KEY_PATH") {
        return path.into();
    }
    std::env::var_os("CREDENTIALS_DIRECTORY")
        .map(PathBuf::from)
        .map(|dir| dir.join("fips.key"))
        .unwrap_or_else(|| "/etc/fips/fips.key".into())
}

pub(crate) fn parse_public_key(key: &str) -> Option<PublicKey> {
    let key = key.trim();
    if key
        .get(..5)
        .is_some_and(|prefix| prefix.eq_ignore_ascii_case("npub1"))
    {
        PublicKey::from_bech32(key).ok()
    } else {
        PublicKey::from_hex(key).ok()
    }
}

fn validate_nonce(nonce: &str) -> Result<(), &'static str> {
    if nonce.len() == 32 && nonce.bytes().all(|b| b.is_ascii_hexdigit()) {
        Ok(())
    } else {
        Err("nonce must be 16 bytes encoded as 32 hex characters")
    }
}

fn builder(nonce: &str, url: &str) -> Result<EventBuilder, String> {
    validate_nonce(nonce).map_err(str::to_string)?;
    let tags = [
        Tag::parse(["nonce", nonce]).map_err(|e| e.to_string())?,
        Tag::parse(["u", url]).map_err(|e| e.to_string())?,
        Tag::parse(["method", "GET"]).map_err(|e| e.to_string())?,
    ];
    Ok(EventBuilder::new(Kind::HttpAuth, "").tags(tags))
}

fn signed_event(keys: &Keys, nonce: &str, url: &str) -> Result<Event, String> {
    builder(nonce, url)?
        .finalize(keys)
        .map_err(|e| format!("sign challenge: {e}"))
}

fn exact_tag<'a>(event: &'a Event, name: &str) -> Option<&'a str> {
    let mut found = event.tags.iter().filter(|tag| tag.kind() == name);
    let tag = found.next()?;
    (found.next().is_none() && tag.len() == 2)
        .then(|| tag.content())
        .flatten()
}

fn verify(event: &Event, expected_key: &str, nonce: &str, url: &str) -> Result<(), String> {
    event.verify().map_err(|e| format!("signature: {e}"))?;
    let expected =
        parse_public_key(expected_key).ok_or_else(|| "expected npub is invalid".to_string())?;
    if event.pubkey != expected {
        return Err("signing pubkey does not match FIPS peer".into());
    }
    if event.kind != Kind::HttpAuth || !event.content.is_empty() || event.tags.len() != 3 {
        return Err("challenge event shape is invalid".into());
    }
    if exact_tag(event, "nonce") != Some(nonce) {
        return Err("nonce tag mismatch".into());
    }
    if exact_tag(event, "u") != Some(url) {
        return Err("u tag mismatch".into());
    }
    if exact_tag(event, "method") != Some("GET") {
        return Err("method tag mismatch".into());
    }
    Ok(())
}

#[derive(Deserialize)]
struct ChallengeQuery {
    nonce: String,
}

#[derive(Deserialize, Serialize)]
struct ChallengeResponse {
    event: Event,
}

async fn handler(
    State(signer): State<Arc<Signer>>,
    Query(query): Query<ChallengeQuery>,
    headers: HeaderMap,
) -> Response {
    let Some(host) = headers.get(header::HOST).and_then(|v| v.to_str().ok()) else {
        return (StatusCode::BAD_REQUEST, "missing Host header").into_response();
    };
    let Ok(authority) = host.parse::<Authority>() else {
        return (StatusCode::BAD_REQUEST, "invalid Host header").into_response();
    };
    let url = format!("http://{authority}{PATH}");
    match signer.sign(&query.nonce, &url) {
        Ok(event) => (
            [(header::CACHE_CONTROL, "no-store")],
            Json(ChallengeResponse { event }),
        )
            .into_response(),
        Err(SignError::BadRequest(e)) => (StatusCode::BAD_REQUEST, e).into_response(),
        Err(SignError::RateLimited) => {
            (StatusCode::TOO_MANY_REQUESTS, "challenge rate limited").into_response()
        }
        Err(SignError::Internal(e)) => {
            tracing::error!(error = %e, "challenge signing failed");
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                "challenge signing failed",
            )
                .into_response()
        }
    }
}

pub fn router(signer: Arc<Signer>) -> Router {
    Router::new().route(PATH, get(handler)).with_state(signer)
}

fn nonce() -> Result<String, String> {
    let mut bytes = [0u8; 16];
    fs::File::open("/dev/urandom")
        .and_then(|mut f| f.read_exact(&mut bytes))
        .map_err(|e| format!("random nonce: {e}"))?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

async fn prove_port(expected_npub: &str, ip: &str, port: u16) -> Result<(), String> {
    let endpoint = http::url(ip, port, PATH).ok_or("peer has no routable address")?;
    let nonce = nonce()?;
    let request_url = format!("{endpoint}?nonce={nonce}");
    let value = tokio::task::spawn_blocking(move || http::get_json(&request_url, None))
        .await
        .map_err(|e| format!("challenge task: {e}"))??;
    let response: ChallengeResponse =
        serde_json::from_value(value).map_err(|e| format!("challenge body: {e}"))?;
    verify(&response.event, expected_npub, &nonce, &endpoint)
}

pub async fn on_candidate(st: Arc<AppState>, npub: &str, ip: &str) {
    // ponytail: one proof attempt per encounter; add bounded retry only if
    // transient challenge misses appear in fleet logs.
    on_candidate_port(st, npub, ip, WEB_PORT).await;
}

async fn on_candidate_port(st: Arc<AppState>, npub: &str, ip: &str, port: u16) {
    let Some(encounter) = st.peer_encounter(npub) else {
        return;
    };
    match prove_port(npub, ip, port).await {
        Ok(()) if st.recognize(npub, encounter) => {
            tracing::info!(npub, "peer recognized as a totem");
            st.push(serde_json::json!({ "type": "totem.recognized", "npub": npub }));
            // ponytail: friendship membership stays empty until the kind-3 reader lands.
            sync::start(st, npub.to_owned(), ip.to_owned(), encounter, false);
        }
        Ok(()) => tracing::debug!(npub, "discarded stale or duplicate challenge result"),
        Err(e) => tracing::info!(npub, error = %e, "challenge failed"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{config::Config, fips::PeerInfo};
    use nostr::{nips::nip19::ToBech32, prelude::Timestamp};
    use std::collections::HashMap;

    fn test_keys(n: u8) -> Keys {
        Keys::parse(&format!("{n:064x}")).unwrap()
    }

    #[test]
    fn signed_proof_is_strict_but_not_clock_dependent() {
        let keys = test_keys(1);
        let npub = keys.public_key().to_bech32().unwrap();
        let nonce = "0123456789abcdef0123456789abcdef";
        let url = "http://[fd00::1]:8080/totem/challenge";
        let event = builder(nonce, url)
            .unwrap()
            .custom_created_at(Timestamp::from_secs(1))
            .finalize(&keys)
            .unwrap();
        assert!(verify(&event, &npub, nonce, url).is_ok());
        assert!(verify(&event, &test_keys(2).public_key().to_hex(), nonce, url).is_err());
        assert!(verify(&event, &npub, "ffffffffffffffffffffffffffffffff", url).is_err());
        assert!(verify(&event, &npub, nonce, "http://wrong/").is_err());

        let mut tampered = event;
        tampered.content = "changed".into();
        assert!(verify(&tampered, &npub, nonce, url).is_err());
    }

    #[test]
    fn bad_nonce_and_signature_rate_are_rejected() {
        let signer = Signer::new(test_keys(1));
        let url = "http://127.0.0.1:8080/totem/challenge";
        assert!(matches!(
            signer.sign("short", url),
            Err(SignError::BadRequest(_))
        ));
        for _ in 0..MAX_SIGNATURES_PER_WINDOW {
            assert!(signer.sign("0123456789abcdef0123456789abcdef", url).is_ok());
        }
        assert!(matches!(
            signer.sign("fedcba9876543210fedcba9876543210", url),
            Err(SignError::RateLimited)
        ));
    }

    #[tokio::test]
    async fn challenge_end_to_end_over_a_real_socket() {
        let keys = test_keys(3);
        let npub = keys.public_key().to_bech32().unwrap();
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        let app = router(Arc::new(Signer::new(keys)));
        let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });

        let st = Arc::new(AppState::new(Config {
            sync: false,
            ..Config::default()
        }));
        let mut peers = HashMap::new();
        peers.insert(
            npub.clone(),
            PeerInfo {
                npub: npub.clone(),
                ipv6_addr: "127.0.0.1".into(),
                transport_type: "test".into(),
                first_seen: 1,
                last_seen: 1,
            },
        );
        st.set_peers(peers);
        let mut pushes = st.tx.subscribe();
        on_candidate_port(st.clone(), &npub, "127.0.0.1", port).await;
        assert!(st.is_recognized(&npub));
        assert_eq!(pushes.try_recv().unwrap()["type"], "totem.recognized");
        server.abort();
    }
}
