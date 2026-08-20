//! Per-encounter strfry sync process supervision.

use std::{
    collections::HashMap,
    path::PathBuf,
    process::Stdio,
    sync::{
        atomic::{AtomicUsize, Ordering},
        Mutex,
    },
    time::{Duration, Instant},
};

use serde_json::{json, Value};
use tokio::{process::Command, sync::oneshot};

use crate::state::AppState;

const RUNNER: &str = "/usr/local/libexec/totem-strfry";
const RELAY_PORT: u16 = 7777;
const DEFAULT_TIMEOUT_SECS: u64 = 300;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SyncState {
    Running,
    Succeeded,
    Failed,
    TimedOut,
    Cancelled,
}

impl SyncState {
    fn as_str(self) -> &'static str {
        match self {
            Self::Running => "running",
            Self::Succeeded => "succeeded",
            Self::Failed => "failed",
            Self::TimedOut => "timed_out",
            Self::Cancelled => "cancelled",
        }
    }
}

struct Job {
    encounter: u64,
    state: SyncState,
    started: Instant,
    duration_ms: Option<u64>,
    exit_code: Option<i32>,
    error: Option<String>,
    cancel: Option<oneshot::Sender<()>>,
}

pub struct SyncSupervisor {
    jobs: Mutex<HashMap<String, Job>>,
    active: AtomicUsize,
    idle: tokio::sync::Notify,
}

impl Default for SyncSupervisor {
    fn default() -> Self {
        Self {
            jobs: Mutex::new(HashMap::new()),
            active: AtomicUsize::new(0),
            idle: tokio::sync::Notify::new(),
        }
    }
}

impl SyncSupervisor {
    /// Reserve exactly one attempt for this peer encounter.
    fn begin(&self, npub: &str, encounter: u64) -> Option<(oneshot::Receiver<()>, Instant)> {
        let mut jobs = self.jobs.lock().unwrap();
        if jobs.get(npub).is_some_and(|job| job.encounter == encounter) {
            return None;
        }
        if let Some(cancel) = jobs.get_mut(npub).and_then(|job| job.cancel.take()) {
            let _ = cancel.send(());
        }
        let (cancel, cancelled) = oneshot::channel();
        let started = Instant::now();
        jobs.insert(
            npub.to_owned(),
            Job {
                encounter,
                state: SyncState::Running,
                started,
                duration_ms: None,
                exit_code: None,
                error: None,
                cancel: Some(cancel),
            },
        );
        self.active.fetch_add(1, Ordering::SeqCst);
        Some((cancelled, started))
    }

    fn finish(
        &self,
        npub: &str,
        encounter: u64,
        state: SyncState,
        duration_ms: u64,
        exit_code: Option<i32>,
        error: Option<String>,
    ) {
        if let Some(job) = self
            .jobs
            .lock()
            .unwrap()
            .get_mut(npub)
            .filter(|job| job.encounter == encounter)
        {
            job.state = state;
            job.duration_ms = Some(duration_ms);
            job.exit_code = exit_code;
            job.error = error;
            job.cancel = None;
        }
        self.active.fetch_sub(1, Ordering::SeqCst);
        self.idle.notify_waiters();
    }

    fn cancel(&self, npub: &str) {
        if let Some(cancel) = self
            .jobs
            .lock()
            .unwrap()
            .get_mut(npub)
            .and_then(|job| job.cancel.take())
        {
            let _ = cancel.send(());
        }
    }

    fn cancel_all(&self) {
        for job in self.jobs.lock().unwrap().values_mut() {
            if let Some(cancel) = job.cancel.take() {
                let _ = cancel.send(());
            }
        }
    }

    async fn wait_idle(&self) {
        loop {
            let notified = self.idle.notified();
            if self.active.load(Ordering::SeqCst) == 0 {
                return;
            }
            notified.await;
        }
    }

    pub fn add_peer_fields(&self, npub: &str, encounter: u64, peer: &mut Value) {
        peer["sync_state"] = Value::Null;
        peer["sync_duration_ms"] = Value::Null;
        peer["sync_exit_code"] = Value::Null;
        peer["sync_error"] = Value::Null;
        let jobs = self.jobs.lock().unwrap();
        let Some(job) = jobs.get(npub).filter(|job| job.encounter == encounter) else {
            return;
        };
        peer["sync_state"] = Value::from(job.state.as_str());
        peer["sync_duration_ms"] = Value::from(
            job.duration_ms
                .unwrap_or_else(|| millis(job.started.elapsed())),
        );
        peer["sync_exit_code"] = job.exit_code.map(Value::from).unwrap_or(Value::Null);
        peer["sync_error"] = job.error.clone().map(Value::from).unwrap_or(Value::Null);
    }
}

fn millis(duration: Duration) -> u64 {
    duration.as_millis().try_into().unwrap_or(u64::MAX)
}

fn relay_url(ip: &str) -> Option<String> {
    if ip.is_empty() {
        return None;
    }
    let host = if ip.contains(':') {
        format!("[{ip}]")
    } else {
        ip.to_owned()
    };
    Some(format!("ws://{host}:{RELAY_PORT}"))
}

fn timeout() -> Duration {
    Duration::from_secs(
        std::env::var("TOTEMD_SYNC_TIMEOUT_SECS")
            .ok()
            .and_then(|value| value.parse().ok())
            .filter(|seconds| *seconds > 0)
            .unwrap_or(DEFAULT_TIMEOUT_SECS),
    )
}

/// Start one bidirectional reconciliation for a recognized encounter.
pub fn start(
    st: std::sync::Arc<AppState>,
    npub: String,
    ip: String,
    encounter: u64,
    is_friend: bool,
) {
    start_with(
        st,
        npub,
        ip,
        encounter,
        is_friend,
        PathBuf::from(RUNNER),
        timeout(),
    );
}

fn start_with(
    st: std::sync::Arc<AppState>,
    npub: String,
    ip: String,
    encounter: u64,
    is_friend: bool,
    runner: PathBuf,
    timeout: Duration,
) {
    if !(st.config().sync || is_friend)
        || !st.is_recognized(&npub)
        || st.peer_encounter(&npub) != Some(encounter)
    {
        return;
    }
    let Some(url) = relay_url(&ip) else {
        return;
    };
    let Some((cancelled, started)) = st.syncs.begin(&npub, encounter) else {
        return;
    };

    tracing::info!(npub, %url, "relay sync started");
    st.push(json!({
        "type": "totem.sync.started",
        "npub": npub,
        "encounter": encounter,
        "direction": "both",
    }));
    tokio::spawn(run(
        st, npub, encounter, url, runner, timeout, started, cancelled,
    ));
}

#[allow(clippy::too_many_arguments)]
async fn run(
    st: std::sync::Arc<AppState>,
    npub: String,
    encounter: u64,
    url: String,
    runner: PathBuf,
    timeout: Duration,
    started: Instant,
    mut cancelled: oneshot::Receiver<()>,
) {
    let mut command = Command::new(&runner);
    command
        .args(["sync", &url, "--dir=both"])
        .env_clear()
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .kill_on_drop(true);
    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(error) => {
            complete(
                &st,
                encounter,
                &npub,
                SyncState::Failed,
                started,
                None,
                Some(format!("start {}: {error}", runner.display())),
            );
            return;
        }
    };

    let (state, exit_code, error) = tokio::select! {
        biased;
        _ = &mut cancelled => {
            let _ = child.kill().await;
            (SyncState::Cancelled, None, None)
        }
        _ = tokio::time::sleep(timeout) => {
            let _ = child.kill().await;
            (SyncState::TimedOut, None, Some(format!("sync exceeded {}s", timeout.as_secs())))
        }
        result = child.wait() => match result {
            Ok(status) if status.success() => (SyncState::Succeeded, status.code(), None),
            Ok(status) => (
                SyncState::Failed,
                status.code(),
                Some(format!("strfry sync {status}")),
            ),
            Err(error) => (SyncState::Failed, None, Some(format!("wait: {error}"))),
        }
    };
    complete(&st, encounter, &npub, state, started, exit_code, error);
}

fn complete(
    st: &AppState,
    encounter: u64,
    npub: &str,
    state: SyncState,
    started: Instant,
    exit_code: Option<i32>,
    error: Option<String>,
) {
    let duration_ms = millis(started.elapsed());
    st.syncs.finish(
        npub,
        encounter,
        state,
        duration_ms,
        exit_code,
        error.clone(),
    );
    tracing::info!(
        npub,
        outcome = state.as_str(),
        duration_ms,
        exit_code,
        error,
        "relay sync finished"
    );
    st.push(json!({
        "type": "totem.sync.done",
        "npub": npub,
        "encounter": encounter,
        "direction": "both",
        "outcome": state.as_str(),
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "error": error,
    }));
}

pub fn cancel(st: &AppState, npub: &str) {
    st.syncs.cancel(npub);
}

pub fn cancel_all(st: &AppState) {
    st.syncs.cancel_all();
}

pub async fn shutdown(st: &AppState) {
    cancel_all(st);
    if tokio::time::timeout(Duration::from_secs(5), st.syncs.wait_idle())
        .await
        .is_err()
    {
        tracing::warn!("timed out waiting for relay sync children to stop");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{config::Config, fips::PeerInfo};
    use std::{
        collections::HashMap,
        fs,
        os::unix::fs::PermissionsExt,
        sync::{atomic::AtomicUsize, Arc},
    };

    static NEXT: AtomicUsize = AtomicUsize::new(0);

    fn peer_state(config: Config, peers: &[(&str, &str, u64)]) -> Arc<AppState> {
        let st = Arc::new(AppState::new(config));
        let map = peers
            .iter()
            .map(|(npub, ip, encounter)| {
                (
                    (*npub).to_owned(),
                    PeerInfo {
                        npub: (*npub).to_owned(),
                        ipv6_addr: (*ip).to_owned(),
                        transport_type: "test".into(),
                        first_seen: *encounter,
                        last_seen: *encounter,
                    },
                )
            })
            .collect::<HashMap<_, _>>();
        st.set_peers(map);
        for (npub, _, encounter) in peers {
            assert!(st.recognize(npub, *encounter));
        }
        st
    }

    fn script(body: &str) -> (PathBuf, PathBuf) {
        let dir = std::env::temp_dir().join(format!(
            "totemd-sync-test-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("runner");
        fs::write(&path, format!("#!/bin/sh\nset -eu\n{body}\n")).unwrap();
        let mut permissions = fs::metadata(&path).unwrap().permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&path, permissions).unwrap();
        (path, dir)
    }

    fn fields(st: &AppState, npub: &str, encounter: u64) -> Value {
        let mut value = json!({});
        st.syncs.add_peer_fields(npub, encounter, &mut value);
        value
    }

    async fn wait_for(st: &AppState, npub: &str, encounter: u64, state: &str) -> Value {
        tokio::time::timeout(Duration::from_secs(2), async {
            loop {
                let value = fields(st, npub, encounter);
                if value["sync_state"] == state {
                    return value;
                }
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .unwrap()
    }

    struct CredentialEnv(Option<std::ffi::OsString>, Option<std::ffi::OsString>);

    impl CredentialEnv {
        fn set() -> Self {
            let old = Self(
                std::env::var_os("CREDENTIALS_DIRECTORY"),
                std::env::var_os("TOTEMD_KEY_PATH"),
            );
            std::env::set_var("CREDENTIALS_DIRECTORY", "/must/not/reach/child");
            std::env::set_var("TOTEMD_KEY_PATH", "/must/not/reach/child.key");
            old
        }
    }

    impl Drop for CredentialEnv {
        fn drop(&mut self) {
            for (name, old) in [
                ("CREDENTIALS_DIRECTORY", self.0.take()),
                ("TOTEMD_KEY_PATH", self.1.take()),
            ] {
                match old {
                    Some(value) => std::env::set_var(name, value),
                    None => std::env::remove_var(name),
                }
            }
        }
    }

    #[tokio::test(flavor = "current_thread")]
    async fn fake_runner_success_deduplicates_and_gets_no_credentials() {
        let marker = std::env::temp_dir().join(format!(
            "totemd-sync-marker-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let (runner, dir) = script(&format!(
            r#"[ "$#" -eq 3 ]
[ "$1" = sync ]
[ "$2" = "ws://127.0.0.1:7777" ]
[ "$3" = "--dir=both" ]
[ -z "${{CREDENTIALS_DIRECTORY+x}}" ]
[ -z "${{TOTEMD_KEY_PATH+x}}" ]
printf started > "{}""#,
            marker.display()
        ));
        let _credentials = CredentialEnv::set();
        let st = peer_state(Config::default(), &[("npub1peer", "127.0.0.1", 1)]);
        let mut pushes = st.tx.subscribe();
        for _ in 0..2 {
            start_with(
                st.clone(),
                "npub1peer".into(),
                "127.0.0.1".into(),
                1,
                false,
                runner.clone(),
                Duration::from_secs(1),
            );
        }
        let value = wait_for(&st, "npub1peer", 1, "succeeded").await;
        assert_eq!(value["sync_exit_code"], 0);
        assert_eq!(fs::read_to_string(&marker).unwrap(), "started");
        assert_eq!(pushes.try_recv().unwrap()["type"], "totem.sync.started");
        assert_eq!(pushes.try_recv().unwrap()["type"], "totem.sync.done");
        assert!(pushes.try_recv().is_err());
        let _ = fs::remove_file(marker);
        fs::remove_dir_all(dir).unwrap();
    }

    #[tokio::test]
    async fn friends_only_policy_failure_and_timeout() {
        let config = Config {
            sync: false,
            ..Config::default()
        };
        let st = peer_state(config, &[("npub1peer", "127.0.0.1", 2)]);
        let (success, success_dir) = script("exit 0");
        start_with(
            st.clone(),
            "npub1peer".into(),
            "127.0.0.1".into(),
            2,
            false,
            success.clone(),
            Duration::from_secs(1),
        );
        assert_eq!(fields(&st, "npub1peer", 2)["sync_state"], Value::Null);
        start_with(
            st.clone(),
            "npub1peer".into(),
            "127.0.0.1".into(),
            2,
            true,
            success,
            Duration::from_secs(1),
        );
        wait_for(&st, "npub1peer", 2, "succeeded").await;
        fs::remove_dir_all(success_dir).unwrap();

        let st = peer_state(Config::default(), &[("npub1fail", "127.0.0.1", 3)]);
        let (failure, failure_dir) = script("exit 7");
        start_with(
            st.clone(),
            "npub1fail".into(),
            "127.0.0.1".into(),
            3,
            false,
            failure,
            Duration::from_secs(1),
        );
        let value = wait_for(&st, "npub1fail", 3, "failed").await;
        assert_eq!(value["sync_exit_code"], 7);
        fs::remove_dir_all(failure_dir).unwrap();

        let st = peer_state(Config::default(), &[("npub1slow", "127.0.0.1", 4)]);
        let (slow, slow_dir) = script("exec /bin/sleep 30");
        start_with(
            st.clone(),
            "npub1slow".into(),
            "127.0.0.1".into(),
            4,
            false,
            slow,
            Duration::from_millis(20),
        );
        wait_for(&st, "npub1slow", 4, "timed_out").await;
        fs::remove_dir_all(slow_dir).unwrap();
    }

    #[tokio::test]
    async fn departure_and_shutdown_cancel_children() {
        let marker = std::env::temp_dir().join(format!(
            "totemd-sync-running-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let (slow, dir) = script(&format!(
            "printf started > \"{}\"\nexec /bin/sleep 30",
            marker.display()
        ));
        let st = peer_state(
            Config::default(),
            &[("npub1a", "127.0.0.1", 5), ("npub1b", "127.0.0.2", 6)],
        );
        start_with(
            st.clone(),
            "npub1a".into(),
            "127.0.0.1".into(),
            5,
            false,
            slow.clone(),
            Duration::from_secs(30),
        );
        tokio::time::timeout(Duration::from_secs(1), async {
            while !marker.exists() {
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .unwrap();
        cancel(&st, "npub1a");
        wait_for(&st, "npub1a", 5, "cancelled").await;

        start_with(
            st.clone(),
            "npub1b".into(),
            "127.0.0.2".into(),
            6,
            false,
            slow,
            Duration::from_secs(30),
        );
        shutdown(&st).await;
        assert_eq!(fields(&st, "npub1b", 6)["sync_state"], "cancelled");
        let _ = fs::remove_file(marker);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn relay_urls_cover_both_ip_families() {
        assert_eq!(relay_url("127.0.0.1").unwrap(), "ws://127.0.0.1:7777");
        assert_eq!(relay_url("fd00::1").unwrap(), "ws://[fd00::1]:7777");
        assert!(relay_url("").is_none());
    }
}
