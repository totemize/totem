//! Shared daemon state and the push side of the bus.
//!
//! Pushes are lossy by design (`07-conventions.md`): consumers reconcile
//! against `totem.status.get` on (re)connect.

use std::{
    collections::{HashMap, VecDeque},
    path::PathBuf,
    sync::{Mutex, RwLock},
    time::Instant,
};

use serde_json::Value;
use tokio::sync::broadcast;

use crate::{
    auth,
    config::{Befriend, Config},
    encounter,
    fips::PeerInfo,
    owner,
    probe::ProbeVerdicts,
    sync::SyncSupervisor,
};

const EVENT_HISTORY_CAPACITY: usize = 256;

pub struct AppState {
    pub started: Instant,
    /// Effective policy: static defaults plus durable owner overrides.
    config: RwLock<Config>,
    pub owner: owner::Store,
    pub auth: auth::Nonces,
    /// NIP-11 probe verdicts per peer npub.
    pub verdicts: ProbeVerdicts,
    /// Fan-out for unsolicited `totem.*` pushes; SSE subscribers tap in.
    pub tx: broadcast::Sender<Value>,
    /// Push counters by type — surfaced via `totem.status.get`.
    counters: Mutex<HashMap<String, u64>>,
    /// Cached kind-1 relay count; `None` means the last count query failed or
    /// has not completed yet, never a fabricated zero.
    note_count: Mutex<Option<u64>>,
    /// Recent pushes for `totem.events.get`; process-local and oldest first.
    event_history: Mutex<VecDeque<Value>>,
    peers: Mutex<HashMap<String, PeerInfo>>,
    /// Authenticated for the current FIPS encounter only; cleared on gone.
    /// The value is the durable history classification made before this
    /// encounter was appended.
    recognized: Mutex<HashMap<String, bool>>,
    encounters: encounter::Store,
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
    #[cfg(test)]
    pub fn new(config: Config) -> Self {
        Self::with_stores(owner::Store::memory(config), encounter::Store::memory())
    }

    pub fn load(config: Config, path: PathBuf) -> Result<Self, String> {
        Self::load_with_paths(config, path, encounter::path())
    }

    fn load_with_paths(
        config: Config,
        owner_path: PathBuf,
        encounter_path: PathBuf,
    ) -> Result<Self, String> {
        Ok(Self::with_stores(
            owner::Store::load(config, owner_path)?,
            encounter::Store::load(encounter_path)?,
        ))
    }

    fn with_stores(owner: owner::Store, encounters: encounter::Store) -> Self {
        let (tx, _) = broadcast::channel(256);
        Self {
            started: Instant::now(),
            config: RwLock::new(owner.effective_config()),
            owner,
            auth: auth::Nonces::default(),
            verdicts: ProbeVerdicts::default(),
            tx,
            counters: Mutex::new(HashMap::new()),
            note_count: Mutex::new(None),
            event_history: Mutex::new(VecDeque::with_capacity(EVENT_HISTORY_CAPACITY)),
            peers: Mutex::new(HashMap::new()),
            recognized: Mutex::new(HashMap::new()),
            encounters,
            syncs: SyncSupervisor::default(),
            mesh: Mutex::new(MeshInfo::default()),
            fips: Mutex::new(FipsHealth::default()),
        }
    }

    pub fn config(&self) -> Config {
        self.config.read().unwrap().clone()
    }

    pub fn update_policy(&self, sync: bool, befriend: Befriend) -> Result<Config, String> {
        let config = self.owner.update_policy(sync, befriend)?;
        *self.config.write().unwrap() = config.clone();
        self.push(serde_json::json!({
            "type": "totem.config.changed",
            "config": config,
        }));
        Ok(config)
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
        let mut history = self.event_history.lock().unwrap();
        if history.len() == EVENT_HISTORY_CAPACITY {
            history.pop_front();
        }
        history.push_back(msg.clone());
        drop(history);
        let _ = self.tx.send(msg);
    }

    pub fn counters(&self) -> HashMap<String, u64> {
        self.counters.lock().unwrap().clone()
    }

    pub fn note_count(&self) -> Option<u64> {
        *self.note_count.lock().unwrap()
    }

    pub fn set_note_count(&self, count: Option<u64>) {
        *self.note_count.lock().unwrap() = count;
    }

    pub fn event_history(&self) -> Vec<Value> {
        self.event_history.lock().unwrap().iter().cloned().collect()
    }

    pub fn peers_map(&self) -> HashMap<String, PeerInfo> {
        self.peers.lock().unwrap().clone()
    }

    pub fn set_peers(&self, peers: HashMap<String, PeerInfo>) {
        self.syncs.observe_live(peers.keys());
        *self.peers.lock().unwrap() = peers;
    }

    pub fn peer_count(&self) -> usize {
        self.peers.lock().unwrap().len()
    }

    pub fn peer_encounter(&self, npub: &str) -> Option<u64> {
        self.peers
            .lock()
            .unwrap()
            .get(npub)
            .map(|peer| peer.first_seen)
    }

    /// Authenticate only the same encounter that issued the challenge.
    /// Returns the peer's durable `known_before` classification for the first
    /// successful proof, `None` for a stale/duplicate proof, and an error when
    /// the append-only history could not be made durable.
    pub fn recognize(&self, npub: &str, encounter: u64) -> Result<Option<bool>, String> {
        let peers = self.peers.lock().unwrap();
        if peers.get(npub).map(|peer| peer.first_seen) != Some(encounter) {
            return Ok(None);
        }
        let mut recognized = self.recognized.lock().unwrap();
        if recognized.contains_key(npub) {
            return Ok(None);
        }
        let known_before = self.encounters.record(npub, encounter)?;
        recognized.insert(npub.into(), known_before);
        Ok(Some(known_before))
    }

    pub fn forget_recognized(&self, npub: &str) {
        self.recognized.lock().unwrap().remove(npub);
    }

    pub fn is_recognized(&self, npub: &str) -> bool {
        self.recognized.lock().unwrap().contains_key(npub)
    }

    pub fn recognized_count(&self) -> usize {
        self.recognized.lock().unwrap().len()
    }

    /// Peers sorted by first arrival, then npub — stable output for the bus —
    /// joined with their probe verdicts (null = not yet probed).
    pub fn peers_snapshot(&self) -> Vec<Value> {
        let mut v: Vec<PeerInfo> = self.peers.lock().unwrap().values().cloned().collect();
        v.extend(self.syncs.departed_peers());
        v.sort_by(|a, b| a.first_seen.cmp(&b.first_seen).then(a.npub.cmp(&b.npub)));
        v.into_iter()
            .map(|p| {
                let mut j = serde_json::to_value(&p).unwrap_or(Value::Null);
                // Sorting means position cannot identify liveness. Consult the
                // current peer map by encounter instead; departed rows are
                // cancellation tombstones, never direct-peer count members.
                let present = self.peer_encounter(&p.npub) == Some(p.first_seen);
                j["present"] = Value::from(present);
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
                let recognized = present
                    .then(|| self.recognized.lock().unwrap().get(&p.npub).copied())
                    .flatten();
                j["recognized"] = Value::from(recognized.is_some());
                j["known_before"] =
                    Value::from(recognized.unwrap_or_else(|| self.encounters.contains(&p.npub)));
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
    use std::{
        fs,
        sync::atomic::{AtomicUsize, Ordering},
    };

    static NEXT: AtomicUsize = AtomicUsize::new(0);
    const PERSISTED_NPUB: &str = "npub1eu0clm0nsxwavcsj07at3sy7v52tuwgw4qpeqsyxgkeqg7krc7ps77c20q";

    fn paths() -> (PathBuf, PathBuf) {
        let suffix = format!(
            "{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        );
        let temp = std::env::temp_dir();
        (
            temp.join(format!("totemd-state-test-{suffix}.toml")),
            temp.join(format!("totemd-history-test-{suffix}.jsonl")),
        )
    }

    fn peer(npub: &str, first_seen: u64) -> PeerInfo {
        PeerInfo {
            npub: npub.into(),
            ipv6_addr: "fd00::1".into(),
            transport_type: "test".into(),
            first_seen,
            last_seen: first_seen,
        }
    }

    #[test]
    fn recognition_lasts_one_encounter() {
        let st = AppState::new(Config::default());
        st.set_peers(HashMap::from([("npub1peer".into(), peer("npub1peer", 1))]));
        assert_eq!(st.recognize("npub1peer", 1).unwrap(), Some(false));
        assert_eq!(st.recognize("npub1peer", 1).unwrap(), None);
        st.forget_recognized("npub1peer");
        st.set_peers(HashMap::from([("npub1peer".into(), peer("npub1peer", 2))]));
        assert_eq!(st.recognize("npub1peer", 1).unwrap(), None); // stale proof
        assert_eq!(st.recognize("npub1peer", 2).unwrap(), Some(true));
    }

    #[test]
    fn known_before_is_stable_for_an_encounter_and_survives_restart() {
        let (owner_path, history_path) = paths();
        let st =
            AppState::load_with_paths(Config::default(), owner_path.clone(), history_path.clone())
                .unwrap();
        st.set_peers(HashMap::from([(
            PERSISTED_NPUB.into(),
            peer(PERSISTED_NPUB, 10),
        )]));
        assert_eq!(st.peers_snapshot()[0]["known_before"], false);
        assert_eq!(st.recognize(PERSISTED_NPUB, 10).unwrap(), Some(false));
        assert_eq!(st.recognize(PERSISTED_NPUB, 10).unwrap(), None);
        assert_eq!(st.peers_snapshot()[0]["known_before"], false);
        assert_eq!(
            fs::read_to_string(&history_path).unwrap().lines().count(),
            1
        );
        drop(st);

        let restarted =
            AppState::load_with_paths(Config::default(), owner_path, history_path.clone()).unwrap();
        restarted.set_peers(HashMap::from([(
            PERSISTED_NPUB.into(),
            peer(PERSISTED_NPUB, 20),
        )]));
        assert_eq!(restarted.peers_snapshot()[0]["known_before"], true);
        assert_eq!(restarted.recognize(PERSISTED_NPUB, 10).unwrap(), None);
        assert_eq!(
            fs::read_to_string(&history_path).unwrap().lines().count(),
            1
        );
        assert_eq!(restarted.recognize(PERSISTED_NPUB, 20).unwrap(), Some(true));
        assert_eq!(restarted.peers_snapshot()[0]["known_before"], true);
        assert_eq!(
            fs::read_to_string(&history_path).unwrap().lines().count(),
            2
        );
        fs::remove_file(history_path).unwrap();
    }

    #[test]
    fn stale_duplicates_and_append_failure_do_not_authenticate() {
        let (owner_path, history_path) = paths();
        let st =
            AppState::load_with_paths(Config::default(), owner_path, history_path.clone()).unwrap();
        st.set_peers(HashMap::from([(
            PERSISTED_NPUB.into(),
            peer(PERSISTED_NPUB, 7),
        )]));
        assert_eq!(st.recognize(PERSISTED_NPUB, 6).unwrap(), None);
        assert!(!history_path.exists());

        fs::create_dir(&history_path).unwrap();
        assert!(st.recognize(PERSISTED_NPUB, 7).is_err());
        assert!(!st.is_recognized(PERSISTED_NPUB));
        assert_eq!(st.peers_snapshot()[0]["known_before"], false);
        fs::remove_dir(history_path).unwrap();
    }
}
