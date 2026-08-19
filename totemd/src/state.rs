//! Shared daemon state and the push side of the bus.
//!
//! Pushes are lossy by design (`07-conventions.md`): consumers reconcile
//! against `totem.status.get` on (re)connect.

use std::{collections::HashMap, sync::Mutex, time::Instant};

use serde_json::Value;
use tokio::sync::broadcast;

pub struct AppState {
    pub started: Instant,
    /// Fan-out for unsolicited `totem.*` pushes; SSE subscribers tap in.
    pub tx: broadcast::Sender<Value>,
    /// Push counters by type — the honest stats surface until the net-code
    /// loop lands real state.
    counters: Mutex<HashMap<String, u64>>,
}

impl AppState {
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(256);
        Self {
            started: Instant::now(),
            tx,
            counters: Mutex::new(HashMap::new()),
        }
    }

    /// Publish an unsolicited push; silently dropped when no subscriber.
    /// First production caller: the net-code loop (fips watch → recognize).
    #[allow(dead_code)]
    pub fn push(&self, msg: Value) {
        if let Some(t) = msg.get("type").and_then(Value::as_str) {
            *self.counters.lock().unwrap().entry(t.to_string()).or_insert(0) += 1;
        }
        let _ = self.tx.send(msg);
    }

    pub fn counters(&self) -> HashMap<String, u64> {
        self.counters.lock().unwrap().clone()
    }
}
