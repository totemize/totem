//! NIP-11 prober and the verdict store (`10-control-plane.md`).
//!
//! On each `totem.peer.seen`: GET the peer's relay port with the NIP-11
//! Accept header; a `!Totem` name prefix + npub claim matching the
//! authenticated transport npub → candidate. Probe verdicts are cached per npub —
//! candidates for the daemon lifetime, non-totems/unreachable re-probed at most once per TTL
//! (a non-totem can install totemd later). In-memory v1; `ponytail:`
//! persist + backoff grades only if re-probe storms ever show in logs.

use std::{collections::HashMap, sync::Mutex};

use serde_json::Value;

use crate::{challenge, http, state::AppState};

/// Standard relay port (`07-conventions.md`; configurable when a
/// non-7777 relay ever exists).
const RELAY_PORT: u16 = 7777;
const MAX_NIP11_NAME_BYTES: usize = 128;

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

/// NIP-11 keys are exactly hex or npub (`07-conventions.md`).
fn key_to_hex(key: &str) -> Option<String> {
    challenge::parse_public_key(key).map(|key| key.to_hex())
}

fn nip11_name(info: &Value) -> Option<String> {
    info.get("name")
        .and_then(Value::as_str)
        .filter(|name| name.len() <= MAX_NIP11_NAME_BYTES && !name.chars().any(char::is_control))
        .map(str::to_owned)
}

/// GET the NIP-11 document. Blocking — call via `spawn_blocking`.
fn fetch_nip11(url: &str) -> Result<Value, String> {
    http::get_json(url, Some("application/nostr+json"))
}

/// Pure: judge a NIP-11 document against the transport-authenticated npub.
fn assess(info: &Value, expected_npub: &str) -> ProbeVerdict {
    let name = info.get("name").and_then(Value::as_str).unwrap_or_default();
    if !name.starts_with("!Totem") {
        return ProbeVerdict::NotTotem;
    }
    let claim = info
        .get("pubkey")
        .and_then(Value::as_str)
        .or_else(|| info.get("self").and_then(Value::as_str))
        .unwrap_or_default();
    match (key_to_hex(claim), key_to_hex(expected_npub)) {
        (Some(a), Some(b)) if a == b => ProbeVerdict::Candidate,
        // Marker present but the claim is missing/garbled/mismatched:
        // not a totem (or not honest about who it is — same treatment).
        _ => ProbeVerdict::NotTotem,
    }
}

/// Probe verdict cache with TTL for negative verdicts; candidates forever.
struct CachedProbe {
    verdict: ProbeVerdict,
    at: u64,
    nip11_name: Option<String>,
}

#[derive(Default)]
pub struct ProbeVerdicts {
    map: Mutex<HashMap<String, CachedProbe>>,
}

fn now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

impl ProbeVerdicts {
    /// Cached verdict if still authoritative (candidate forever, else within ttl).
    fn get(&self, npub: &str, ttl_hours: u64) -> Option<ProbeVerdict> {
        let map = self.map.lock().unwrap();
        let cached = map.get(npub)?;
        match cached.verdict {
            ProbeVerdict::Candidate => Some(cached.verdict),
            _ if now().saturating_sub(cached.at) < ttl_hours.saturating_mul(3600) => {
                Some(cached.verdict)
            }
            _ => None,
        }
    }

    #[cfg(test)]
    fn set(&self, npub: &str, verdict: ProbeVerdict) {
        self.set_with_name(npub, verdict, None);
    }

    pub fn set_with_name(&self, npub: &str, verdict: ProbeVerdict, nip11_name: Option<String>) {
        self.map.lock().unwrap().insert(
            npub.into(),
            CachedProbe {
                verdict,
                at: now(),
                nip11_name,
            },
        );
    }

    pub fn details(&self, npub: &str) -> Option<(ProbeVerdict, Option<String>)> {
        self.map
            .lock()
            .unwrap()
            .get(npub)
            .map(|cached| (cached.verdict, cached.nip11_name.clone()))
    }

    #[cfg(test)]
    fn get_freshness(&self, npub: &str) -> Option<(ProbeVerdict, u64)> {
        self.map
            .lock()
            .unwrap()
            .get(npub)
            .map(|cached| (cached.verdict, cached.at))
    }
}

/// Probe-triggered-by-seen handler. Cheap paths first: probe disabled →
/// out; fresh verdict → maybe push `totem.peer.candidate` (per-encounter) and
/// out; only then one fetch.
pub async fn on_seen(st: std::sync::Arc<AppState>, npub: &str, ip: &str) {
    if on_seen_port(&st, npub, ip, RELAY_PORT).await == Some(ProbeVerdict::Candidate) {
        challenge::on_candidate(st, npub, ip).await;
    }
}

async fn on_seen_port(st: &AppState, npub: &str, ip: &str, port: u16) -> Option<ProbeVerdict> {
    if !st.config.probe {
        return None;
    }
    if let Some(v) = st.verdicts.get(npub, st.config.verdict_ttl_hours) {
        if v == ProbeVerdict::Candidate {
            push_candidate(st, npub);
        }
        return Some(v);
    }
    let url = http::url(ip, port, "/");
    let (verdict, name) = match url {
        Some(u) => match tokio::task::spawn_blocking(move || fetch_nip11(&u)).await {
            Ok(Ok(info)) => {
                let verdict = assess(&info, npub);
                let name = if verdict == ProbeVerdict::Candidate {
                    nip11_name(&info)
                } else {
                    None
                };
                (verdict, name)
            }
            Ok(Err(e)) => {
                tracing::debug!(npub, error = %e, "probe fetch failed");
                (ProbeVerdict::Unreachable, None)
            }
            Err(e) => {
                tracing::warn!(npub, error = %e, "probe task failed");
                (ProbeVerdict::Unreachable, None)
            }
        },
        None => (ProbeVerdict::Unreachable, None),
    };
    tracing::info!(npub, verdict = verdict.as_str(), "probe verdict");
    st.verdicts.set_with_name(npub, verdict, name);
    if verdict == ProbeVerdict::Candidate {
        push_candidate(st, npub);
    }
    Some(verdict)
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
    fn key_parsing_accepts_only_hex_and_npub() {
        assert_eq!(key_to_hex(N_PUB).unwrap(), HEX);
        assert_eq!(key_to_hex(&N_PUB.to_uppercase()).unwrap(), HEX);
        assert_eq!(key_to_hex(HEX).unwrap(), HEX);
        assert_eq!(key_to_hex(&HEX.to_uppercase()).unwrap(), HEX);
        assert!(key_to_hex("npub1badchecksumzz").is_none());
        assert!(key_to_hex(&format!("nostr:{N_PUB}")).is_none());
        assert!(key_to_hex("not-a-key").is_none());
    }

    #[test]
    fn nip11_name_hint_is_bounded_and_terminal_safe() {
        assert_eq!(
            nip11_name(&json!({"name": "!Totem motown"})).as_deref(),
            Some("!Totem motown")
        );
        assert!(nip11_name(&json!({"name": "!Totem\nspoof"})).is_none());
        assert!(nip11_name(&json!({"name": "x".repeat(129)})).is_none());
    }

    #[test]
    fn assess_verdicts() {
        let ok = json!({"name": "!Totem motown", "pubkey": HEX});
        assert_eq!(assess(&ok, N_PUB), ProbeVerdict::Candidate);
        // bech32 claim, same key
        let ok2 = json!({"name": "!Totem x", "pubkey": N_PUB});
        assert_eq!(assess(&ok2, N_PUB), ProbeVerdict::Candidate);
        // legacy/self duplicate, same key
        let self_claim = json!({"name": "!Totem x", "self": N_PUB});
        assert_eq!(assess(&self_claim, N_PUB), ProbeVerdict::Candidate);
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
        // candidates cached regardless
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
        assert_eq!(
            st.verdicts.details(N_PUB).unwrap().1.as_deref(),
            Some("!Totem fake")
        );
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
