//! fips control-socket client and peer watcher.
//!
//! Protocol: JSON-lines over the daemon's Unix socket
//! (`{"command":"show_peers"}` → `{"status":"ok","data":{...}}`) — a direct
//! client, never a `fipsctl` shell-out (`10-control-plane.md`). Reconnects
//! per query: the socket is cheap, statelessness is worth it at poll rates.

use std::{
    collections::HashMap,
    path::PathBuf,
    sync::Arc,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

use serde::Serialize;
use serde_json::{json, Value};
use tokio::{
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader},
    net::UnixStream,
};

use crate::{probe, state::AppState, sync};

#[derive(Clone, Debug, Serialize)]
pub struct PeerInfo {
    pub npub: String,
    pub ipv6_addr: String,
    pub transport_type: String,
    pub first_seen: u64,
    pub last_seen: u64,
}

#[derive(Clone, Debug)]
pub struct FipsSnapshot {
    pub own_npub: String,
    pub mesh_size: u64,
    pub peers: HashMap<String, PeerInfo>,
}

fn sock_path() -> PathBuf {
    std::env::var("TOTEMD_FIPS_SOCK")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/run/fips/control.sock"))
}

pub async fn query(cmd: &str) -> Result<Value, String> {
    query_at(&sock_path(), cmd).await
}

pub async fn query_at(path: &std::path::Path, cmd: &str) -> Result<Value, String> {
    let stream = UnixStream::connect(path)
        .await
        .map_err(|e| format!("connect {}: {e}", path.display()))?;
    let (r, mut w) = stream.into_split();
    let mut reader = BufReader::new(r);

    let req = json!({ "command": cmd });
    w.write_all(format!("{req}\n").as_bytes())
        .await
        .map_err(|e| format!("write {cmd}: {e}"))?;

    let mut line = String::new();
    reader
        .read_line(&mut line)
        .await
        .map_err(|e| format!("read {cmd}: {e}"))?;

    let resp: Value =
        serde_json::from_str(line.trim()).map_err(|e| format!("parse {cmd} response: {e}"))?;
    match resp.get("status").and_then(Value::as_str) {
        Some("ok") => Ok(resp["data"].clone()),
        _ => Err(format!(
            "{cmd} error: {}",
            resp.get("message").and_then(Value::as_str).unwrap_or("?")
        )),
    }
}

/// Pure: turn a `show_peers` + `show_status` pair into a snapshot.
pub fn parse_snapshot(peers: &Value, status: &Value) -> FipsSnapshot {
    let mut map = HashMap::new();
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    for p in peers
        .get("peers")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or_default()
    {
        let s = |k: &str| {
            p.get(k)
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string()
        };
        let npub = s("npub");
        if npub.is_empty() {
            continue;
        }
        map.insert(
            npub.to_string(),
            PeerInfo {
                npub: npub.to_string(),
                ipv6_addr: s("ipv6_addr"),
                transport_type: s("transport_type"),
                first_seen: now,
                last_seen: now,
            },
        );
    }
    FipsSnapshot {
        own_npub: status
            .get("npub")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string(),
        mesh_size: status
            .get("estimated_mesh_size")
            .and_then(Value::as_u64)
            .unwrap_or(0),
        peers: map,
    }
}

/// Pure: merge a new snapshot into the old peer map, preserving first_seen,
/// and return (arrivals, departures) by npub.
pub fn diff(
    old: &HashMap<String, PeerInfo>,
    new: FipsSnapshot,
) -> (HashMap<String, PeerInfo>, Vec<String>, Vec<String>) {
    let mut merged = new.peers;
    let mut seen = Vec::new();
    for (npub, p) in merged.iter_mut() {
        if let Some(prev) = old.get(npub) {
            p.first_seen = prev.first_seen;
        } else {
            seen.push(npub.clone());
        }
    }
    let gone: Vec<String> = old
        .keys()
        .filter(|k| !merged.contains_key(*k))
        .cloned()
        .collect();
    (merged, seen, gone)
}

/// Watcher loop: poll fips, update state, emit `totem.peer.seen` /
/// `totem.peer.gone` pushes. The first poll emits `seen` for peers that
/// were already connected — consumers get current state as events too.
/// Losses are impossible here (state is swapped atomically); SSE delivery
/// stays lossy per `07-conventions.md`.
pub async fn watch(st: Arc<AppState>) {
    let poll = Duration::from_millis(
        std::env::var("TOTEMD_FIPS_POLL_MS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(2000),
    );
    let mut warned = false;
    loop {
        match tick(&st).await {
            Ok(()) => {
                if warned {
                    tracing::info!("fips control socket recovered");
                    warned = false;
                }
            }
            Err(e) => {
                st.set_fips(false, Some(e.clone()));
                if !warned {
                    tracing::warn!("fips control socket: {e}");
                    warned = true;
                } else {
                    tracing::debug!("fips control socket: {e}");
                }
            }
        }
        tokio::time::sleep(poll).await;
    }
}

async fn tick(st: &Arc<AppState>) -> Result<(), String> {
    let peers = query("show_peers").await?;
    let status = query("show_status").await?;
    let snap = parse_snapshot(&peers, &status);
    let (own_npub, mesh_size) = (snap.own_npub.clone(), snap.mesh_size);
    let previous = st.peers_map();
    let (merged, seen, gone) = diff(&previous, snap);
    let seen_info: Vec<(String, String)> = seen
        .iter()
        .filter_map(|npub| {
            merged
                .get(npub)
                .map(|peer| (npub.clone(), peer.ipv6_addr.clone()))
        })
        .collect();

    // Publish current state before pushes/tasks so immediate reconciliation
    // cannot observe the previous snapshot.
    st.set_fips(true, None);
    st.set_peers(merged);
    st.set_mesh(own_npub, mesh_size);
    for npub in &gone {
        if let Some(peer) = previous.get(npub) {
            sync::depart(st, peer);
        }
    }

    for (npub, ip) in seen_info {
        tracing::info!(npub, "peer seen");
        st.push(json!({ "type": "totem.peer.seen", "npub": npub }));
        let st = st.clone();
        tokio::spawn(async move { probe::on_seen(st, &npub, &ip).await });
    }
    for npub in &gone {
        st.forget_recognized(npub);
        tracing::info!(npub, "peer gone");
        st.push(json!({ "type": "totem.peer.gone", "npub": npub }));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    /// Minimal fake fips control socket: one JSON-lines response per
    /// request, canned per command — exercises query_at end to end.
    async fn fake_fips(path: &std::path::Path) -> std::io::Result<()> {
        let listener = tokio::net::UnixListener::bind(path)?;
        tokio::spawn(async move {
            while let Ok((s, _)) = listener.accept().await {
                tokio::spawn(async move {
                    let (r, mut w) = s.into_split();
                    let mut line = String::new();
                    let mut reader = BufReader::new(r);
                    while reader.read_line(&mut line).await.unwrap_or(0) > 0 {
                        let cmd: Value = serde_json::from_str(line.trim()).unwrap();
                        let resp = match cmd["command"].as_str().unwrap() {
                            "show_peers" => json!({"status":"ok","data":{"peers":[{
                                "npub":"npub1peer","ipv6_addr":"fd00::42",
                                "transport_type":"udp"}]}}),
                            "show_status" => json!({"status":"ok","data":{
                                "npub":"npub1self","estimated_mesh_size":2}}),
                            other => {
                                json!({"status":"error","message":format!("unknown command: {other}")})
                            }
                        };
                        w.write_all(format!("{resp}\n").as_bytes()).await.unwrap();
                        line.clear();
                    }
                });
            }
        });
        Ok(())
    }

    #[tokio::test]
    async fn query_round_trip_against_fake_socket() {
        let unique = format!("totemd-fips-test-{}", std::process::id());
        let path = std::env::temp_dir().join(unique);
        let _ = std::fs::remove_file(&path);
        fake_fips(&path).await.unwrap();
        let peers = query_at(&path, "show_peers").await.unwrap();
        assert_eq!(peers["peers"][0]["npub"], "npub1peer");
        let err = query_at(&path, "show_nope").await;
        assert!(err.is_err());
        // Socket gone → error, not panic.
        std::fs::remove_file(&path).unwrap();
        assert!(query_at(&path, "show_peers").await.is_err());
    }

    #[test]
    fn parse_snapshot_fields() {
        let peers = json!({"peers":[
            {"npub":"npub1a","ipv6_addr":"fd00::1","transport_type":"udp"},
            {"npub":"npub1b","transport_type":"tcp"},
            {"ipv6_addr":"fd00::3"} // no npub → skipped
        ]});
        let status = json!({"npub":"npub1me","estimated_mesh_size":5});
        let s = parse_snapshot(&peers, &status);
        assert_eq!(s.own_npub, "npub1me");
        assert_eq!(s.mesh_size, 5);
        assert_eq!(s.peers.len(), 2);
        assert_eq!(s.peers["npub1b"].ipv6_addr, "");
    }

    #[test]
    fn diff_detects_arrivals_departures_and_preserves_first_seen() {
        let old: HashMap<String, PeerInfo> = [
            (
                "npub1old".to_string(),
                PeerInfo {
                    npub: "npub1old".into(),
                    ipv6_addr: "fd00::9".into(),
                    transport_type: "udp".into(),
                    first_seen: 100,
                    last_seen: 100,
                },
            ),
            (
                "npub1stay".to_string(),
                PeerInfo {
                    npub: "npub1stay".into(),
                    ipv6_addr: "fd00::8".into(),
                    transport_type: "udp".into(),
                    first_seen: 50,
                    last_seen: 50,
                },
            ),
        ]
        .into_iter()
        .collect();
        let new = parse_snapshot(
            &json!({"peers":[{"npub":"npub1stay"},{"npub":"npub1new"}]}),
            &json!({"npub":"npub1me","estimated_mesh_size":1}),
        );
        let (merged, seen, gone) = diff(&old, new);
        assert_eq!(seen, vec!["npub1new".to_string()]);
        assert_eq!(gone, vec!["npub1old".to_string()]);
        assert_eq!(merged["npub1stay"].first_seen, 50); // preserved
        assert!(merged["npub1new"].first_seen >= 1_700_000_000); // now
    }
}
