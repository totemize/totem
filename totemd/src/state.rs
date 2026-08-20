//! Shared daemon state and the push side of the bus.
//!
//! Pushes are lossy by design (`07-conventions.md`): consumers reconcile
//! against `totem.status.get` on (re)connect.

use std::{
    collections::HashMap,
    sync::Mutex,
    time::Instant,
};

use serde_json::Value;
use tokio::sync::broadcast;

use crate::fips::PeerInfo;

pub struct AppState {
    pub started: Instant,
    /// Fan-out for unsolicited `totem.*` pushes; SSE subscribers tap in.
    pub tx: broadcast::Sender<Value>,
    /// Push counters by type — surfaced via `totem.status.get`.
    counters: Mutex<HashMap<String, u64>>,
    peers: Mutex<HashMap<String, PeerInfo>>,
    /// fips-side identity/mesh info from the last successful poll.
    mesh: Mutex<MeshInfo>,
    /// Connectivity health of the fips control socket.
    fips: Mutex<FipsHealth>,
}

#[derive(Default, Clone)]
struct MeshInfo {
    own_npub: String,
    size: u64,
}

#[derive(Default)]
struct FipsHealth {
    ok: bool,
    last_ok: Option<Instant>,
    last_err: Option<String>,
}

impl AppState {
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(256);
        Self {
            started: Instant::now(),
            tx,
            counters: Mutex::new(HashMap::new()),
            peers: Mutex::new(HashMap::new()),
            mesh: Mutex::new(MeshInfo::default()),
            fips: Mutex::new(FipsHealth::default()),
        }
    }

    /// Publish an unsolicited push; silently dropped when no subscriber.
    pub fn push(&self, msg: Value) {
        if let Some(t) = msg.get("type").and_then(Value::as_str) {
            *self.counters.lock().unwrap().entry(t.to_string()).or_insert(0) += 1;
        }
        let _ = self.tx.send(msg);
    }

    pub fn counters(&self) -> HashMap<String, u64> {
        self.counters.lock().unwrap().clone()
    }

    pub fn peers_map(&self) -> HashMap<String, PeerInfo> {
        self.peers.lock().unwrap().clone()
    }

    pub fn set_peers(&self, peers: HashMap<String, PeerInfo>) {
        *self.peers.lock().unwrap() = peers;
    }

    /// Peers sorted by first arrival, then npub — stable output for the bus.
    pub fn peers_snapshot(&self) -> Vec<PeerInfo> {
        let mut v: Vec<PeerInfo> = self.peers.lock().unwrap().values().cloned().collect();
        v.sort_by(|a, b| a.first_seen.cmp(&b.first_seen).then(a.npub.cmp(&b.npub)));
        v
    }

    pub fn set_mesh(&self, own_npub: String, size: u64) {
        *self.mesh.lock().unwrap() = MeshInfo { own_npub, size };
    }

    pub fn set_fips(&self, ok: bool, err: Option<String>) {
        let mut h = self.fips.lock().unwrap();
        h.ok = ok;
        if ok {
            h.last_ok = Some(Instant::now());
            h.last_err = None;
        } else {
            h.last_err = err;
        }
    }

    pub fn fips_json(&self) -> Value {
        let h = self.fips.lock().unwrap();
        let m = self.mesh.lock().unwrap();
        let age = |t: Option<Instant>| {
            t.map(|i| i.elapsed().as_secs()).map(Value::from).unwrap_or(Value::Null)
        };
        serde_json::json!({
            "connected": h.ok,
            "npub": if m.own_npub.is_empty() { Value::Null } else { Value::from(m.own_npub.clone()) },
            "mesh_size": m.size,
            "last_ok_secs_ago": age(h.last_ok),
            "last_error": h.last_err.clone().map(Value::from).unwrap_or(Value::Null),
        })
    }
}
