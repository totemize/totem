//! Shared daemon state and the push side of the bus.
//!
//! Pushes are lossy by design (`07-conventions.md`): consumers reconcile
//! against `totem.status.get` on (re)connect.

use std::{
    collections::{HashMap, HashSet},
    sync::Mutex,
    time::Instant,
};

use serde_json::Value;
use tokio::sync::broadcast;

use crate::{config::Config, fips::PeerInfo, probe::ProbeVerdicts, sync::SyncSupervisor};

pub struct AppState {
    pub started: Instant,
    /// Effective operator policy (`10-control-plane.md`); read-only.
    pub config: Config,
    /// NIP-11 probe verdicts per peer npub.
    pub verdicts: ProbeVerdicts,
    /// Fan-out for unsolicited `totem.*` pushes; SSE subscribers tap in.
    pub tx: broadcast::Sender<Value>,
    /// Push counters by type — surfaced via `totem.status.get`.
    counters: Mutex<HashMap<String, u64>>,
    peers: Mutex<HashMap<String, PeerInfo>>,
    /// Authenticated for the current FIPS encounter only; cleared on gone.
    recognized: Mutex<HashSet<String>>,
    pub(crate) syncs: SyncSupervisor,
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
    pub fn new(config: Config) -> Self {
        let (tx, _) = broadcast::channel(256);
        Self {
            started: Instant::now(),
            config,
            verdicts: ProbeVerdicts::default(),
            tx,
            counters: Mutex::new(HashMap::new()),
            peers: Mutex::new(HashMap::new()),
            recognized: Mutex::new(HashSet::new()),
            syncs: SyncSupervisor::default(),
            mesh: Mutex::new(MeshInfo::default()),
            fips: Mutex::new(FipsHealth::default()),
        }
    }

    /// Publish an unsolicited push; silently dropped when no subscriber.
    pub fn push(&self, msg: Value) {
        if let Some(t) = msg.get("type").and_then(Value::as_str) {
            *self
                .counters
                .lock()
                .unwrap()
                .entry(t.to_string())
                .or_insert(0) += 1;
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

    pub fn peer_encounter(&self, npub: &str) -> Option<u64> {
        self.peers
            .lock()
            .unwrap()
            .get(npub)
            .map(|peer| peer.first_seen)
    }

    /// Authenticate only the same encounter that issued the challenge.
    /// Returns true for its first successful proof.
    pub fn recognize(&self, npub: &str, encounter: u64) -> bool {
        let peers = self.peers.lock().unwrap();
        if peers.get(npub).map(|peer| peer.first_seen) != Some(encounter) {
            return false;
        }
        self.recognized.lock().unwrap().insert(npub.into())
    }

    pub fn forget_recognized(&self, npub: &str) {
        self.recognized.lock().unwrap().remove(npub);
    }

    pub fn is_recognized(&self, npub: &str) -> bool {
        self.recognized.lock().unwrap().contains(npub)
    }

    pub fn recognized_count(&self) -> usize {
        self.recognized.lock().unwrap().len()
    }

    /// Peers sorted by first arrival, then npub — stable output for the bus —
    /// joined with their probe verdicts (null = not yet probed).
    pub fn peers_snapshot(&self) -> Vec<Value> {
        let mut v: Vec<PeerInfo> = self.peers.lock().unwrap().values().cloned().collect();
        v.sort_by(|a, b| a.first_seen.cmp(&b.first_seen).then(a.npub.cmp(&b.npub)));
        v.into_iter()
            .map(|p| {
                let mut j = serde_json::to_value(&p).unwrap_or(Value::Null);
                match self.verdicts.details(&p.npub) {
                    Some((verdict, name)) => {
                        j["probe_verdict"] = Value::from(verdict.as_str());
                        j["nip11_name"] = name.map(Value::from).unwrap_or(Value::Null);
                    }
                    None => {
                        j["probe_verdict"] = Value::Null;
                        j["nip11_name"] = Value::Null;
                    }
                }
                j["recognized"] = Value::from(self.is_recognized(&p.npub));
                self.syncs.add_peer_fields(&p.npub, p.first_seen, &mut j);
                j
            })
            .collect()
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
            t.map(|i| i.elapsed().as_secs())
                .map(Value::from)
                .unwrap_or(Value::Null)
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recognition_lasts_one_encounter() {
        let st = AppState::new(Config::default());
        let peer = |first_seen| PeerInfo {
            npub: "npub1peer".into(),
            ipv6_addr: "fd00::1".into(),
            transport_type: "test".into(),
            first_seen,
            last_seen: first_seen,
        };
        st.set_peers(HashMap::from([("npub1peer".into(), peer(1))]));
        assert!(st.recognize("npub1peer", 1));
        assert!(!st.recognize("npub1peer", 1));
        st.forget_recognized("npub1peer");
        st.set_peers(HashMap::from([("npub1peer".into(), peer(2))]));
        assert!(!st.recognize("npub1peer", 1)); // stale proof
        assert!(st.recognize("npub1peer", 2));
    }
}
