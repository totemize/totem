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
                "events": st.counters(),
            });
        }
        // Net-code loop (fips watch → recognize → sync) lands next;
        // honest empty until then.
        "totem.peers.get" => out["peers"] = json!([]),
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
}
