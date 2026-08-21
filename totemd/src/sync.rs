//! Periodic per-encounter strfry sync process supervision.

use std::{
    collections::{HashMap, HashSet, VecDeque},
    io::Write,
    path::{Path, PathBuf},
    process::Stdio,
    sync::{
        atomic::{AtomicUsize, Ordering},
        Mutex,
    },
    time::{Duration, Instant},
};

use serde_json::{json, Value};
use tokio::{
    io::{AsyncBufReadExt, BufReader},
    process::{ChildStderr, Command},
    sync::oneshot,
};

use crate::{fips::PeerInfo, state::AppState};

const RUNNER: &str = "/usr/local/libexec/totem-strfry";
const RELAY_PORT: u16 = 7777;
const DEFAULT_TIMEOUT_SECS: u64 = 300;
const DEFAULT_INTERVAL_SECS: u64 = 300;
const DEPARTED_SNAPSHOT_CAPACITY: usize = 64;

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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct ReconcileDelta {
    missing_remote: u64,
    missing_local: u64,
}

struct Job {
    encounter: u64,
    attempt: u64,
    state: SyncState,
    started: Instant,
    duration_ms: Option<u64>,
    exit_code: Option<i32>,
    error: Option<String>,
    cancel: Option<oneshot::Sender<()>>,
}

pub struct SyncSupervisor {
    jobs: Mutex<HashMap<String, Job>>,
    /// Recently departed peers whose cancellation payoff must remain visible
    /// to snapshot-only consumers. Replacement encounters remove their prior
    /// row and the fixed capacity prevents unbounded history growth.
    departed: Mutex<VecDeque<PeerInfo>>,
    active: AtomicUsize,
    idle: tokio::sync::Notify,
}

impl Default for SyncSupervisor {
    fn default() -> Self {
        Self {
            jobs: Mutex::new(HashMap::new()),
            departed: Mutex::new(VecDeque::with_capacity(DEPARTED_SNAPSHOT_CAPACITY)),
            active: AtomicUsize::new(0),
            idle: tokio::sync::Notify::new(),
        }
    }
}

impl SyncSupervisor {
    /// Reserve exactly one reconciliation loop for this peer encounter.
    fn begin(&self, npub: &str, encounter: u64) -> Option<(oneshot::Receiver<()>, u64, Instant)> {
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
                attempt: 1,
                state: SyncState::Running,
                started,
                duration_ms: None,
                exit_code: None,
                error: None,
                cancel: Some(cancel),
            },
        );
        self.active.fetch_add(1, Ordering::SeqCst);
        Some((cancelled, 1, started))
    }

    fn next_attempt(&self, npub: &str, encounter: u64) -> Option<(u64, Instant)> {
        let mut jobs = self.jobs.lock().unwrap();
        let job = jobs
            .get_mut(npub)
            .filter(|job| job.encounter == encounter && job.cancel.is_some())?;
        job.attempt += 1;
        job.state = SyncState::Running;
        job.started = Instant::now();
        job.duration_ms = None;
        job.exit_code = None;
        job.error = None;
        Some((job.attempt, job.started))
    }

    #[allow(clippy::too_many_arguments)]
    fn finish_attempt(
        &self,
        npub: &str,
        encounter: u64,
        attempt: u64,
        state: SyncState,
        duration_ms: u64,
        exit_code: Option<i32>,
        error: Option<String>,
    ) {
        if let Some(job) = self.jobs.lock().unwrap().get_mut(npub).filter(|job| {
            job.encounter == encounter
                && job.attempt == attempt
                && job.state != SyncState::Cancelled
        }) {
            job.state = state;
            job.duration_ms = Some(duration_ms);
            job.exit_code = exit_code;
            job.error = error;
        }
    }

    fn finish_loop(&self, npub: &str, encounter: u64) {
        if let Some(job) = self
            .jobs
            .lock()
            .unwrap()
            .get_mut(npub)
            .filter(|job| job.encounter == encounter)
        {
            job.cancel = None;
        }
        self.active.fetch_sub(1, Ordering::SeqCst);
        self.idle.notify_waiters();
    }

    #[cfg(test)]
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

    /// Cancel a departing peer and retain a bounded, explicitly non-live row
    /// until a replacement encounter arrives (or the retention cap evicts it).
    fn depart(&self, peer: &PeerInfo) {
        let (cancel, was_running) = {
            let mut jobs = self.jobs.lock().unwrap();
            let Some(job) = jobs
                .get_mut(&peer.npub)
                .filter(|job| job.encounter == peer.first_seen)
            else {
                return;
            };
            let was_running = job.state == SyncState::Running && job.cancel.is_some();
            if was_running {
                job.state = SyncState::Cancelled;
                job.duration_ms = Some(millis(job.started.elapsed()));
                job.exit_code = None;
                job.error = None;
            }
            (job.cancel.take(), was_running)
        };
        if let Some(cancel) = cancel {
            let _ = cancel.send(());
        }
        if !was_running {
            // A completed round may still own the cancellation sender while
            // its periodic loop sleeps. Stop that loop, but do not rewrite its
            // truthful terminal outcome into a departure cancellation.
            self.remove_terminal_job(peer);
            return;
        }

        let evicted = {
            let mut departed = self.departed.lock().unwrap();
            departed.retain(|entry| entry.npub != peer.npub || entry.first_seen != peer.first_seen);
            departed.push_back(peer.clone());
            (departed.len() > DEPARTED_SNAPSHOT_CAPACITY)
                .then(|| departed.pop_front())
                .flatten()
        };
        if let Some(evicted) = evicted {
            self.remove_terminal_job(&evicted);
        }
    }

    /// Purge tombstones as soon as any replacement/live encounter is present,
    /// so an old cancellation token can never attach to a new peer row.
    pub(crate) fn observe_live<'a>(&self, npubs: impl Iterator<Item = &'a String>) {
        let live: HashSet<&str> = npubs.map(String::as_str).collect();
        let removed: Vec<PeerInfo> = {
            let mut departed = self.departed.lock().unwrap();
            let removed = departed
                .iter()
                .filter(|peer| live.contains(peer.npub.as_str()))
                .cloned()
                .collect();
            departed.retain(|peer| !live.contains(peer.npub.as_str()));
            removed
        };
        for peer in removed {
            self.remove_terminal_job(&peer);
        }
    }

    fn remove_terminal_job(&self, peer: &PeerInfo) {
        let mut jobs = self.jobs.lock().unwrap();
        if jobs
            .get(&peer.npub)
            .is_some_and(|job| job.encounter == peer.first_seen && job.cancel.is_none())
        {
            jobs.remove(&peer.npub);
        }
    }

    pub(crate) fn departed_peers(&self) -> Vec<PeerInfo> {
        self.departed.lock().unwrap().iter().cloned().collect()
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
        peer["sync_attempt"] = Value::Null;
        peer["sync_state"] = Value::Null;
        peer["sync_duration_ms"] = Value::Null;
        peer["sync_exit_code"] = Value::Null;
        peer["sync_error"] = Value::Null;
        let jobs = self.jobs.lock().unwrap();
        let Some(job) = jobs.get(npub).filter(|job| job.encounter == encounter) else {
            return;
        };
        peer["sync_attempt"] = Value::from(job.attempt);
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

fn parse_reconcile_delta(line: &str) -> Option<ReconcileDelta> {
    let (_, counts) = line.split_once("Set reconcile complete. Have ")?;
    let (have, need) = counts.split_once(" need ")?;
    Some(ReconcileDelta {
        missing_remote: have.parse().ok()?,
        missing_local: need.split_whitespace().next()?.parse().ok()?,
    })
}

fn parse_reconcile_summary(line: &str) -> Option<String> {
    // ponytail: pinned strfry has no machine report; keep its readable summary
    // authoritative and make parsed counts optional until upstream emits JSON.
    let start = line.find("Set reconcile complete.")?;
    Some(line[start..].trim().to_owned())
}

async fn drain_stderr(stderr: ChildStderr) -> Option<String> {
    let mut lines = BufReader::new(stderr).lines();
    let mut summary = None;
    while let Ok(Some(line)) = lines.next_line().await {
        summary = parse_reconcile_summary(&line).or(summary);
        let _ = writeln!(std::io::stderr().lock(), "{line}");
    }
    summary
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

fn interval() -> Duration {
    Duration::from_secs(
        std::env::var("TOTEMD_SYNC_INTERVAL_SECS")
            .ok()
            .and_then(|value| value.parse().ok())
            .filter(|seconds| *seconds > 0)
            .unwrap_or(DEFAULT_INTERVAL_SECS),
    )
}

fn eligible(st: &AppState, npub: &str, encounter: u64, is_friend: bool) -> bool {
    (st.config().sync || is_friend)
        && st.is_recognized(npub)
        && st.peer_encounter(npub) == Some(encounter)
}

/// Start periodic bidirectional reconciliation for a recognized encounter.
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
        interval(),
    );
}

#[allow(clippy::too_many_arguments)]
fn start_with(
    st: std::sync::Arc<AppState>,
    npub: String,
    ip: String,
    encounter: u64,
    is_friend: bool,
    runner: PathBuf,
    timeout: Duration,
    interval: Duration,
) {
    if !eligible(&st, &npub, encounter, is_friend) {
        return;
    }
    let Some(url) = relay_url(&ip) else {
        return;
    };
    let Some((cancelled, attempt, started)) = st.syncs.begin(&npub, encounter) else {
        return;
    };

    push_started(&st, &npub, encounter, attempt, &url);
    tokio::spawn(run_loop(
        st, npub, encounter, is_friend, url, runner, timeout, interval, attempt, started, cancelled,
    ));
}

fn push_started(st: &AppState, npub: &str, encounter: u64, attempt: u64, url: &str) {
    tracing::info!(npub, attempt, %url, "relay sync started");
    st.push(json!({
        "type": "totem.sync.started",
        "npub": npub,
        "encounter": encounter,
        "attempt": attempt,
        "direction": "both",
    }));
}

#[allow(clippy::too_many_arguments)]
async fn run_loop(
    st: std::sync::Arc<AppState>,
    npub: String,
    encounter: u64,
    is_friend: bool,
    url: String,
    runner: PathBuf,
    timeout: Duration,
    interval: Duration,
    mut attempt: u64,
    mut started: Instant,
    mut cancelled: oneshot::Receiver<()>,
) {
    loop {
        let (state, exit_code, error, summary) =
            run_attempt(&runner, &url, timeout, &mut cancelled).await;
        complete_attempt(
            &st, encounter, attempt, &npub, state, started, exit_code, error, summary,
        );
        if state == SyncState::Cancelled {
            break;
        }

        tokio::select! {
            biased;
            _ = &mut cancelled => break,
            _ = tokio::time::sleep(interval) => {}
        }
        if !eligible(&st, &npub, encounter, is_friend) {
            break;
        }
        let Some(next) = st.syncs.next_attempt(&npub, encounter) else {
            break;
        };
        (attempt, started) = next;
        push_started(&st, &npub, encounter, attempt, &url);
    }
    st.syncs.finish_loop(&npub, encounter);
}

async fn run_attempt(
    runner: &Path,
    url: &str,
    timeout: Duration,
    cancelled: &mut oneshot::Receiver<()>,
) -> (SyncState, Option<i32>, Option<String>, Option<String>) {
    let mut command = Command::new(runner);
    command
        .args(["sync", url, "--dir=both"])
        .env_clear()
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(error) => {
            return (
                SyncState::Failed,
                None,
                Some(format!("start {}: {error}", runner.display())),
                None,
            );
        }
    };
    let stderr = child.stderr.take().expect("piped child stderr");
    let stderr_task = tokio::spawn(drain_stderr(stderr));

    let result = tokio::select! {
        biased;
        _ = cancelled => {
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
            Err(error) => {
                let _ = child.kill().await;
                (SyncState::Failed, None, Some(format!("wait: {error}")))
            }
        }
    };
    let summary = stderr_task.await.unwrap_or(None);
    (result.0, result.1, result.2, summary)
}

#[allow(clippy::too_many_arguments)]
fn complete_attempt(
    st: &AppState,
    encounter: u64,
    attempt: u64,
    npub: &str,
    state: SyncState,
    started: Instant,
    exit_code: Option<i32>,
    error: Option<String>,
    summary: Option<String>,
) {
    let duration_ms = millis(started.elapsed());
    let delta = summary.as_deref().and_then(parse_reconcile_delta);
    let missing_remote = delta.map(|delta| delta.missing_remote);
    let missing_local = delta.map(|delta| delta.missing_local);
    st.syncs.finish_attempt(
        npub,
        encounter,
        attempt,
        state,
        duration_ms,
        exit_code,
        error.clone(),
    );
    tracing::info!(
        npub,
        attempt,
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
        "attempt": attempt,
        "direction": "both",
        "outcome": state.as_str(),
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "error": error,
        "summary": summary,
        "missing_remote": missing_remote,
        "missing_local": missing_local,
    }));
}

#[cfg(test)]
pub fn cancel(st: &AppState, npub: &str) {
    st.syncs.cancel(npub);
}

pub fn depart(st: &AppState, peer: &PeerInfo) {
    st.syncs.depart(peer);
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
            assert!(st.recognize(npub, *encounter).unwrap().is_some());
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
        wait_for_attempt(st, npub, encounter, None, state).await
    }

    async fn wait_for_attempt(
        st: &AppState,
        npub: &str,
        encounter: u64,
        attempt: Option<u64>,
        state: &str,
    ) -> Value {
        // Sync tests spawn real child processes. Leave headroom for loaded
        // macOS/CI runners while retaining a finite failure bound.
        tokio::time::timeout(Duration::from_secs(5), async {
            loop {
                let value = fields(st, npub, encounter);
                if value["sync_state"] == state
                    && attempt.is_none_or(|attempt| value["sync_attempt"] == attempt)
                {
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
    async fn periodic_success_deduplicates_and_gets_no_credentials() {
        let marker = std::env::temp_dir().join(format!(
            "totemd-sync-marker-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let lock = marker.with_extension("lock");
        let (runner, dir) = script(&format!(
            r#"[ "$#" -eq 3 ]
[ "$1" = sync ]
[ "$2" = "ws://127.0.0.1:7777" ]
[ "$3" = "--dir=both" ]
[ -z "${{CREDENTIALS_DIRECTORY+x}}" ]
[ -z "${{TOTEMD_KEY_PATH+x}}" ]
[ ! -e "{lock}" ]
touch "{lock}"
n=0; [ ! -e "{marker}" ] || n=$(cat "{marker}")
echo $((n + 1)) > "{marker}"
echo 'test INFO| Set reconcile complete. Have 3 need 2' >&2
sleep 0.02
rm "{lock}""#,
            lock = lock.display(),
            marker = marker.display(),
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
                Duration::from_millis(50),
            );
        }
        let value = wait_for_attempt(&st, "npub1peer", 1, Some(2), "succeeded").await;
        assert_eq!(value["sync_exit_code"], 0);
        cancel(&st, "npub1peer");
        st.syncs.wait_idle().await;
        tokio::time::sleep(Duration::from_millis(75)).await;
        assert_eq!(fs::read_to_string(&marker).unwrap().trim(), "2");
        for (typ, attempt) in [
            ("totem.sync.started", 1),
            ("totem.sync.done", 1),
            ("totem.sync.started", 2),
            ("totem.sync.done", 2),
        ] {
            let push = pushes.try_recv().unwrap();
            assert_eq!(push["type"], typ);
            assert_eq!(push["attempt"], attempt);
            if typ == "totem.sync.done" {
                assert_eq!(push["summary"], "Set reconcile complete. Have 3 need 2");
                assert_eq!(push["missing_remote"], 3);
                assert_eq!(push["missing_local"], 2);
            }
        }
        assert!(pushes.try_recv().is_err());
        let _ = fs::remove_file(marker);
        fs::remove_dir_all(dir).unwrap();
    }

    #[tokio::test]
    async fn policy_failure_and_timeout_retry() {
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
            Duration::from_secs(30),
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
            Duration::from_secs(30),
        );
        wait_for(&st, "npub1peer", 2, "succeeded").await;
        shutdown(&st).await;
        fs::remove_dir_all(success_dir).unwrap();

        let marker = std::env::temp_dir().join(format!(
            "totemd-sync-failure-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let (failure, failure_dir) = script(&format!(
            "n=0; [ ! -e \"{0}\" ] || n=$(cat \"{0}\")\n\
             echo $((n + 1)) > \"{0}\"\n[ $n -ge 1 ]",
            marker.display()
        ));
        let st = peer_state(Config::default(), &[("npub1fail", "127.0.0.1", 3)]);
        start_with(
            st.clone(),
            "npub1fail".into(),
            "127.0.0.1".into(),
            3,
            false,
            failure,
            Duration::from_secs(1),
            Duration::from_millis(20),
        );
        wait_for_attempt(&st, "npub1fail", 3, Some(2), "succeeded").await;
        shutdown(&st).await;
        assert_eq!(fs::read_to_string(&marker).unwrap().trim(), "2");
        let _ = fs::remove_file(marker);
        fs::remove_dir_all(failure_dir).unwrap();

        let marker = std::env::temp_dir().join(format!(
            "totemd-sync-timeout-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let (slow, slow_dir) = script(&format!(
            "if [ ! -e \"{0}\" ]; then touch \"{0}\"; exec /bin/sleep 30; fi",
            marker.display()
        ));
        let st = peer_state(Config::default(), &[("npub1slow", "127.0.0.1", 4)]);
        start_with(
            st.clone(),
            "npub1slow".into(),
            "127.0.0.1".into(),
            4,
            false,
            slow,
            // Process startup can exceed 20 ms on loaded/macOS runners. The
            // first attempt still deterministically times out against its
            // 30-second sleep; the retry has enough time to exit successfully.
            Duration::from_millis(500),
            Duration::from_millis(20),
        );
        wait_for_attempt(&st, "npub1slow", 4, Some(2), "succeeded").await;
        assert!(st.event_history().iter().any(|event| {
            event["type"] == "totem.sync.done"
                && event["attempt"] == 1
                && event["outcome"] == "timed_out"
        }));
        shutdown(&st).await;
        let _ = fs::remove_file(marker);
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
            Duration::from_secs(30),
        );
        shutdown(&st).await;
        assert_eq!(fields(&st, "npub1b", 6)["sync_state"], "cancelled");
        let _ = fs::remove_file(marker);
        fs::remove_dir_all(dir).unwrap();
    }

    #[tokio::test]
    async fn departed_cancellation_survives_snapshot_and_expires_on_reencounter() {
        let (slow, dir) = script("exec /bin/sleep 30");
        let st = peer_state(Config::default(), &[("npub1farewell", "127.0.0.1", 7)]);
        start_with(
            st.clone(),
            "npub1farewell".into(),
            "127.0.0.1".into(),
            7,
            false,
            slow,
            Duration::from_secs(30),
            Duration::from_secs(30),
        );
        wait_for(&st, "npub1farewell", 7, "running").await;

        let departed = st.peers_map().remove("npub1farewell").unwrap();
        depart(&st, &departed);
        st.set_peers(HashMap::new());
        st.forget_recognized("npub1farewell");

        let snapshot = st.peers_snapshot();
        assert_eq!(st.peer_count(), 0);
        assert_eq!(snapshot.len(), 1);
        assert_eq!(snapshot[0]["npub"], "npub1farewell");
        assert_eq!(snapshot[0]["first_seen"], 7);
        assert_eq!(snapshot[0]["present"], false);
        assert_eq!(snapshot[0]["recognized"], false);
        assert_eq!(snapshot[0]["sync_state"], "cancelled");
        assert_eq!(snapshot[0]["sync_attempt"], 1);
        let status = crate::bus::handle(json!({"type": "totem.status.get"}), &st);
        let peers = crate::bus::handle(json!({"type": "totem.peers.get"}), &st);
        assert_eq!(status["status"]["peers"], 0);
        assert_eq!(peers["peers"].as_array().unwrap().len(), 1);
        assert_eq!(peers["peers"][0]["present"], false);
        st.syncs.wait_idle().await;

        let replacement = PeerInfo {
            npub: "npub1farewell".into(),
            ipv6_addr: "127.0.0.2".into(),
            transport_type: "test".into(),
            first_seen: 8,
            last_seen: 8,
        };
        st.set_peers(HashMap::from([("npub1farewell".into(), replacement)]));
        let snapshot = st.peers_snapshot();
        assert_eq!(st.peer_count(), 1);
        assert_eq!(snapshot.len(), 1);
        assert_eq!(snapshot[0]["first_seen"], 8);
        assert_eq!(snapshot[0]["present"], true);
        assert_eq!(snapshot[0]["sync_state"], Value::Null);

        fs::remove_dir_all(dir).unwrap();
    }

    #[tokio::test]
    async fn departure_after_completed_round_does_not_fabricate_cancellation() {
        let (success, dir) = script("exit 0");
        let st = peer_state(Config::default(), &[("npub1complete", "127.0.0.1", 9)]);
        start_with(
            st.clone(),
            "npub1complete".into(),
            "127.0.0.1".into(),
            9,
            false,
            success,
            Duration::from_secs(1),
            Duration::from_secs(30),
        );
        wait_for(&st, "npub1complete", 9, "succeeded").await;

        let departed = st.peers_map().remove("npub1complete").unwrap();
        depart(&st, &departed);
        st.set_peers(HashMap::new());
        st.forget_recognized("npub1complete");
        st.syncs.wait_idle().await;

        assert!(st.peers_snapshot().is_empty());
        assert!(st.syncs.departed_peers().is_empty());
        assert!(!st.syncs.jobs.lock().unwrap().contains_key("npub1complete"));
        assert!(!st.event_history().iter().any(|event| {
            event["type"] == "totem.sync.done" && event["outcome"] == "cancelled"
        }));

        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn departed_snapshot_retention_is_bounded_and_evicts_terminal_jobs() {
        let supervisor = SyncSupervisor::default();
        for encounter in 0..=DEPARTED_SNAPSHOT_CAPACITY as u64 {
            let npub = format!("npub1peer{encounter}");
            let _cancelled = supervisor.begin(&npub, encounter).unwrap();
            supervisor.depart(&PeerInfo {
                npub,
                ipv6_addr: format!("fd00::{encounter:x}"),
                transport_type: "test".into(),
                first_seen: encounter,
                last_seen: encounter,
            });
        }

        let retained = supervisor.departed_peers();
        assert_eq!(retained.len(), DEPARTED_SNAPSHOT_CAPACITY);
        assert_eq!(retained.first().unwrap().first_seen, 1);
        assert_eq!(retained.last().unwrap().first_seen, 64);
        assert_eq!(
            supervisor.jobs.lock().unwrap().len(),
            DEPARTED_SNAPSHOT_CAPACITY
        );
        assert!(!supervisor.jobs.lock().unwrap().contains_key("npub1peer0"));
    }

    #[test]
    fn reconciliation_summary_survives_count_format_changes() {
        let summary =
            parse_reconcile_summary("2026-08-20 INFO| Set reconcile complete. Have 12 need 3")
                .unwrap();
        assert_eq!(summary, "Set reconcile complete. Have 12 need 3");
        assert_eq!(
            parse_reconcile_delta(&summary),
            Some(ReconcileDelta {
                missing_remote: 12,
                missing_local: 3,
            })
        );

        let summary =
            parse_reconcile_summary("INFO| Set reconcile complete. format changed").unwrap();
        assert_eq!(summary, "Set reconcile complete. format changed");
        assert_eq!(parse_reconcile_delta(&summary), None);
        assert!(parse_reconcile_summary("INFO| unrelated").is_none());
    }

    #[test]
    fn relay_urls_cover_both_ip_families() {
        assert_eq!(relay_url("127.0.0.1").unwrap(), "ws://127.0.0.1:7777");
        assert_eq!(relay_url("fd00::1").unwrap(), "ws://[fd00::1]:7777");
        assert!(relay_url("").is_none());
    }
}
