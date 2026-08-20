//! The bus dispatcher: NIP-5D-shaped request/result (`07-conventions.md`).
//!
//! Requests arrive as `{ "type": "domain.action", "id": ..., ...payload }`;
//! results are `{ "type": "<action>.result", "id": ..., "ok": bool, ... }`.

use serde_json::{json, Value};

use crate::state::AppState;

pub fn handle(msg: Value, st: &AppState) -> Value {
    let typ = msg
        .get("type")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    let mut out = json!({ "type": format!("{typ}.result"), "ok": true });
    if let Some(id) = msg.get("id") {
        out["id"] = id.clone();
    }
    match typ.as_str() {
        "totem.status.get" => {
            out["status"] = json!({
                "version": env!("CARGO_PKG_VERSION"),
                "uptime_secs": st.started.elapsed().as_secs(),
                "fips": st.fips_json(),
                "peers": st.peers_snapshot().len(),
                "events": st.counters(),
            });
        }
        "totem.peers.get" => {
            out["peers"] = serde_json::to_value(st.peers_snapshot())
                .unwrap_or_else(|_| json!([]));
        }
        "totem.contacts.add" | "totem.contacts.remove" => {
            out["ok"] = json!(false);
            out["error"] = json!("contacts writer not implemented (kind 3 single writer lands with net code)");
        }
        _ => {
            out["ok"] = json!(false);
            out["error"] = json!(format!("unknown type: {typ}"));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn status_round_trip() {
        let st = AppState::new();
        let r = handle(json!({"type": "totem.status.get", "id": "a1"}), &st);
        assert_eq!(r["type"], "totem.status.get.result");
        assert_eq!(r["id"], "a1");
        assert_eq!(r["ok"], true);
        assert_eq!(r["status"]["version"], env!("CARGO_PKG_VERSION"));
    }

    #[test]
    fn unknown_type_is_an_error_result() {
        let st = AppState::new();
        let r = handle(json!({"type": "totem.nope", "id": "a2"}), &st);
        assert_eq!(r["type"], "totem.nope.result");
        assert_eq!(r["ok"], false);
        assert!(r["error"].is_string());
    }

    #[test]
    fn push_counts_by_type() {
        let st = AppState::new();
        st.push(json!({"type": "totem.peer.seen"}));
        st.push(json!({"type": "totem.peer.seen"}));
        st.push(json!({"type": "totem.sync.done"}));
        let r = handle(json!({"type": "totem.status.get"}), &st);
        assert_eq!(r["status"]["events"]["totem.peer.seen"], 2);
        assert_eq!(r["status"]["events"]["totem.sync.done"], 1);
    }

    #[tokio::test]
    async fn peers_get_returns_watcher_state() {
        use crate::fips::PeerInfo;
        use std::collections::HashMap;
        let st = AppState::new();
        let mut m = HashMap::new();
        m.insert(
            "npub1aa".into(),
            PeerInfo {
                npub: "npub1aa".into(),
                ipv6_addr: "fd00::1".into(),
                transport_type: "udp".into(),
                first_seen: 7,
                last_seen: 9,
            },
        );
        st.set_peers(m);
        let r = handle(json!({"type": "totem.peers.get", "id": "p1"}), &st);
        assert_eq!(r["type"], "totem.peers.get.result");
        assert_eq!(r["peers"][0]["npub"], "npub1aa");
        assert_eq!(r["peers"][0]["ipv6_addr"], "fd00::1");
        assert_eq!(r["status"], serde_json::Value::Null); // no stale fields
    }
}
