//! NIP-11 prober and the verdict store (`10-control-plane.md`).
//!
//! On each `totem.peer.seen`: GET the peer's relay port with the NIP-11
//! Accept header; a `!Totem` name prefix + npub claim matching the
//! authenticated transport npub → candidate. Probe verdicts are cached per npub —
//! candidates for the daemon lifetime, non-totems/unreachable re-probed at most once per TTL
//! (a non-totem can install totemd later). In-memory v1; `ponytail:`
//! persist + backoff grades only if re-probe storms ever show in logs.

use std::{collections::HashMap, sync::Mutex, time::Duration};

use bech32::FromBase32;
use serde_json::Value;

use crate::state::AppState;

/// Standard relay port (`07-conventions.md`; configurable when a
/// non-7777 relay ever exists).
pub const RELAY_PORT: u16 = 7777;
const FETCH_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_NIP11_BYTES: u64 = 64 * 1024;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeVerdict {
    Candidate,
    NotTotem,
    Unreachable,
}

impl ProbeVerdict {
    pub fn as_str(&self) -> &'static str {
        match self {
            ProbeVerdict::Candidate => "candidate",
            ProbeVerdict::NotTotem => "not_totem",
            ProbeVerdict::Unreachable => "unreachable",
        }
    }
}

/// npub (bech32) → lowercase hex.
pub fn npub_to_hex(npub: &str) -> Option<String> {
    let (hrp, data, variant) = bech32::decode(npub).ok()?;
    if hrp != "npub" || variant != bech32::Variant::Bech32 {
        return None;
    }
    let bytes: Vec<u8> = Vec::from_base32(&data).ok()?;
    if bytes.len() != 32 {
        return None;
    }
    Some(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

/// NIP-11 `pubkey` claims may be hex or bech32 (`07-conventions.md`).
fn claim_to_hex(claim: &str) -> Option<String> {
    let c = claim.trim();
    if c.len() == 64 && c.chars().all(|ch| ch.is_ascii_hexdigit()) {
        Some(c.to_lowercase())
    } else {
        npub_to_hex(c)
    }
}

/// GET the NIP-11 document. Blocking — call via `spawn_blocking`.
pub fn fetch_nip11(url: &str) -> Result<Value, String> {
    use std::io::Read;

    let agent = ureq::AgentBuilder::new().timeout(FETCH_TIMEOUT).build();
    let response = agent
        .get(url)
        .set("Accept", "application/nostr+json")
        .call()
        .map_err(|e| format!("GET {url}: {e}"))?;
    let mut body = String::new();
    response
        .into_reader()
        .take(MAX_NIP11_BYTES + 1)
        .read_to_string(&mut body)
        .map_err(|e| format!("body: {e}"))?;
    if body.len() as u64 > MAX_NIP11_BYTES {
        return Err(format!("body exceeds {MAX_NIP11_BYTES} bytes"));
    }
    serde_json::from_str(&body).map_err(|e| format!("body: {e}"))
}

/// Pure: judge a NIP-11 document against the transport-authenticated npub.
pub fn assess(info: &Value, expected_npub: &str) -> ProbeVerdict {
    let name = info.get("name").and_then(Value::as_str).unwrap_or_default();
    if !name.starts_with("!Totem") {
        return ProbeVerdict::NotTotem;
    }
    let claim = info
        .get("pubkey")
        .and_then(Value::as_str)
        .unwrap_or_default();
    match (claim_to_hex(claim), npub_to_hex(expected_npub)) {
        (Some(a), Some(b)) if a == b => ProbeVerdict::Candidate,
        // Marker present but the claim is missing/garbled/mismatched:
        // not a totem (or not honest about who it is — same treatment).
        _ => ProbeVerdict::NotTotem,
    }
}

/// Probe verdict cache with TTL for negative verdicts; candidates forever.
#[derive(Default)]
pub struct ProbeVerdicts {
    map: Mutex<HashMap<String, (ProbeVerdict, u64)>>, // npub -> (verdict, unix-secs)
}

fn now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

impl ProbeVerdicts {
    /// Cached verdict if still authoritative (totem forever, else within ttl).
    pub fn get(&self, npub: &str, ttl_hours: u64) -> Option<ProbeVerdict> {
        let (v, at) = *self.map.lock().unwrap().get(npub)?;
        match v {
            ProbeVerdict::Candidate => Some(v),
            _ if now().saturating_sub(at) < ttl_hours.saturating_mul(3600) => Some(v),
            _ => None,
        }
    }

    pub fn set(&self, npub: &str, v: ProbeVerdict) {
        self.map.lock().unwrap().insert(npub.into(), (v, now()));
    }

    pub fn get_freshness(&self, npub: &str) -> Option<(ProbeVerdict, u64)> {
        self.map.lock().unwrap().get(npub).copied()
    }
}

/// Probe-triggered-by-seen handler. Cheap paths first: probe disabled →
/// out; fresh verdict → maybe push `totem.peer.candidate` (per-encounter) and
/// out; only then one fetch.
pub async fn on_seen(st: &AppState, npub: &str, ip: &str) {
    on_seen_port(st, npub, ip, RELAY_PORT).await
}

pub async fn on_seen_port(st: &AppState, npub: &str, ip: &str, port: u16) {
    if !st.config.probe {
        return;
    }
    if let Some(v) = st.verdicts.get(npub, st.config.verdict_ttl_hours) {
        if v == ProbeVerdict::Candidate {
            push_candidate(st, npub);
        }
        return;
    }
    let url = if ip.is_empty() {
        None // peer without a routable address: record and retry next encounter
    } else {
        // Brackets are IPv6-only: `http://[fd00::1]:7777/` vs `http://192.168.8.136:7777/`
        let host = if ip.contains(':') {
            format!("[{ip}]")
        } else {
            ip.to_string()
        };
        Some(format!("http://{host}:{port}/"))
    };
    let verdict = match url {
        Some(u) => match tokio::task::spawn_blocking(move || fetch_nip11(&u)).await {
            Ok(Ok(info)) => assess(&info, npub),
            Ok(Err(e)) => {
                tracing::debug!(npub, error = %e, "probe fetch failed");
                ProbeVerdict::Unreachable
            }
            Err(e) => {
                tracing::warn!(npub, error = %e, "probe task failed");
                ProbeVerdict::Unreachable
            }
        },
        None => ProbeVerdict::Unreachable,
    };
    tracing::info!(npub, verdict = verdict.as_str(), "probe verdict");
    st.verdicts.set(npub, verdict);
    if verdict == ProbeVerdict::Candidate {
        push_candidate(st, npub);
    }
}

fn push_candidate(st: &AppState, npub: &str) {
    tracing::info!(npub, "peer is a totem candidate");
    st.push(serde_json::json!({ "type": "totem.peer.candidate", "npub": npub }));
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    const N_PUB: &str = "npub1eu0clm0nsxwavcsj07at3sy7v52tuwgw4qpeqsyxgkeqg7krc7ps77c20q";
    const HEX: &str = "cf1f8fedf3819dd662127fbab8c09e6514be390ea80390408645b2047ac3c783";

    #[test]
    fn npub_hex_roundtrip() {
        use bech32::ToBase32;

        assert_eq!(npub_to_hex(N_PUB).unwrap(), HEX);
        assert!(npub_to_hex("npub1badchecksumzz").is_none());
        let short = bech32::encode("npub", [1u8].to_base32(), bech32::Variant::Bech32).unwrap();
        assert!(npub_to_hex(&short).is_none());
        let wrong_variant =
            bech32::encode("npub", [1u8; 32].to_base32(), bech32::Variant::Bech32m).unwrap();
        assert!(npub_to_hex(&wrong_variant).is_none());
    }

    #[test]
    fn claim_accepts_hex_and_bech32() {
        assert_eq!(claim_to_hex(HEX).unwrap(), HEX);
        assert_eq!(claim_to_hex(&HEX.to_uppercase()).unwrap(), HEX);
        assert_eq!(claim_to_hex(N_PUB).unwrap(), HEX);
        assert!(claim_to_hex("not-a-key").is_none());
    }

    #[test]
    fn assess_verdicts() {
        let ok = json!({"name": "!Totem motown", "pubkey": HEX});
        assert_eq!(assess(&ok, N_PUB), ProbeVerdict::Candidate);
        // bech32 claim, same key
        let ok2 = json!({"name": "!Totem x", "pubkey": N_PUB});
        assert_eq!(assess(&ok2, N_PUB), ProbeVerdict::Candidate);
        // marker only, no claim
        let nokey = json!({"name": "!Totem x"});
        assert_eq!(assess(&nokey, N_PUB), ProbeVerdict::NotTotem);
        // marker but different key
        let wrong = json!({"name": "!Totem x", "pubkey": "00".repeat(32)});
        assert_eq!(assess(&wrong, N_PUB), ProbeVerdict::NotTotem);
        // ordinary relay
        let relay = json!({"name": "wss.nostr.example", "pubkey": HEX});
        assert_eq!(assess(&relay, N_PUB), ProbeVerdict::NotTotem);
    }

    #[test]
    fn verdict_cache_tiers() {
        let v = ProbeVerdicts::default();
        v.set("a", ProbeVerdict::NotTotem);
        v.set("b", ProbeVerdict::Candidate);
        // fresh negatives served
        assert_eq!(v.get("a", 24), Some(ProbeVerdict::NotTotem));
        // zero ttl → any negative is stale
        assert_eq!(v.get("a", 0), None);
        // totems cached regardless
        assert_eq!(v.get("b", 0), Some(ProbeVerdict::Candidate));
    }

    /// End-to-end against a real socket: fake relay serves NIP-11, probe
    /// stores the verdict and pushes `totem.peer.candidate` on the bus.
    #[tokio::test]
    async fn probe_end_to_end_with_fake_relay() {
        use crate::config::Config;
        use std::sync::{
            atomic::{AtomicUsize, Ordering},
            Arc,
        };
        let st = Arc::new(AppState::new(Config::default()));

        let body = json!({"name": "!Totem fake", "pubkey": HEX}).to_string();
        let l = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = l.local_addr().unwrap().port();
        let hits = Arc::new(AtomicUsize::new(0));
        let server_hits = hits.clone();
        tokio::spawn(async move {
            loop {
                let Ok((mut s, _)) = l.accept().await else {
                    continue;
                };
                server_hits.fetch_add(1, Ordering::Relaxed);
                let mut buf = [0u8; 1024];
                use tokio::io::AsyncReadExt;
                let _ = s.read(&mut buf).await; // drain request
                let resp = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/nostr+json\r\n\
                     Content-Length: {}\r\nConnection: close\r\n\r\n{body}",
                    body.len()
                );
                use tokio::io::AsyncWriteExt;
                let _ = s.write_all(resp.as_bytes()).await;
            }
        });

        let mut sub = st.tx.subscribe();
        on_seen_port(&st, N_PUB, "127.0.0.1", port).await;
        assert_eq!(st.verdicts.get(N_PUB, 24), Some(ProbeVerdict::Candidate));
        assert_eq!(hits.load(Ordering::Relaxed), 1);
        let msg = sub.try_recv().unwrap();
        assert_eq!(msg["type"], "totem.peer.candidate");
        assert_eq!(msg["npub"], N_PUB);

        // cached: second encounter pushes candidate again, no new fetch
        let before = st.verdicts.get_freshness(N_PUB).unwrap().1;
        on_seen_port(&st, N_PUB, "127.0.0.1", port).await;
        assert_eq!(st.verdicts.get_freshness(N_PUB).unwrap().1, before);
        assert_eq!(hits.load(Ordering::Relaxed), 1); // cache: no second GET
        assert_eq!(sub.try_recv().unwrap()["type"], "totem.peer.candidate");

        // dead port → unreachable verdict
        on_seen_port(&st, "npub1dead", "127.0.0.1", 1).await;
        assert_eq!(
            st.verdicts.get("npub1dead", 24),
            Some(ProbeVerdict::Unreachable)
        );
    }

    #[tokio::test]
    async fn probe_disabled_skips_everything() {
        use std::sync::Arc;
        let c = crate::config::Config {
            probe: false,
            befriend: crate::config::Befriend::Never,
            ..Default::default()
        };
        let st = Arc::new(AppState::new(c));
        on_seen_port(&st, N_PUB, "127.0.0.1", 1).await; // port 1: would fail loudly
        assert_eq!(st.verdicts.get_freshness(N_PUB), None); // never touched
    }
}
