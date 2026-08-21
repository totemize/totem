//! Cached relay facts for status and presentation consumers.

use std::{path::Path, path::PathBuf, sync::Arc, time::Duration};

use tokio::process::Command;

use crate::state::AppState;

const RUNNER: &str = "/usr/local/libexec/totem-strfry";
const NOTE_FILTER: &str = r#"{"kinds":[1]}"#;
const POLL_INTERVAL: Duration = Duration::from_secs(15);
const QUERY_TIMEOUT: Duration = Duration::from_secs(5);

pub async fn watch(st: Arc<AppState>) {
    loop {
        match count_notes_with(&runner_path()).await {
            Ok(count) => {
                st.set_note_count(Some(count));
                tracing::debug!(count, "relay note count refreshed");
            }
            Err(error) => {
                st.set_note_count(None);
                tracing::warn!(%error, "relay note count unavailable");
            }
        }
        tokio::time::sleep(POLL_INTERVAL).await;
    }
}

async fn count_notes_with(runner: &Path) -> Result<u64, String> {
    let mut command = Command::new(runner);
    command
        .args(["scan", "--count", NOTE_FILTER])
        .kill_on_drop(true);
    let output = tokio::time::timeout(QUERY_TIMEOUT, command.output())
        .await
        .map_err(|_| format!("{} note count timed out", runner.display()))?
        .map_err(|error| format!("start {} note count: {error}", runner.display()))?;
    if !output.status.success() {
        let error = String::from_utf8_lossy(&output.stderr);
        return Err(format!(
            "{} note count exited {}: {}",
            runner.display(),
            output.status,
            error.trim()
        ));
    }
    parse_count(&output.stdout)
}

fn parse_count(output: &[u8]) -> Result<u64, String> {
    let value = std::str::from_utf8(output)
        .map_err(|_| "strfry note count was not UTF-8".to_string())?
        .trim();
    if value.is_empty() || value.lines().count() != 1 {
        return Err("strfry note count was not one decimal line".into());
    }
    value
        .parse()
        .map_err(|_| format!("invalid strfry note count: {value}"))
}

fn runner_path() -> PathBuf {
    std::env::var_os("TOTEMD_STRFRY_RUNNER")
        .map(PathBuf::from)
        .unwrap_or_else(|| RUNNER.into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        fs,
        os::unix::fs::PermissionsExt,
        sync::atomic::{AtomicUsize, Ordering},
    };

    static NEXT: AtomicUsize = AtomicUsize::new(0);

    fn runner(body: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "totemd-relay-count-test-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::write(&path, format!("#!/bin/sh\nset -eu\n{body}\n")).unwrap();
        let mut permissions = fs::metadata(&path).unwrap().permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&path, permissions).unwrap();
        path
    }

    #[test]
    fn count_parser_is_strict_and_bounded_to_u64() {
        assert_eq!(parse_count(b"404\n").unwrap(), 404);
        assert!(parse_count(b"").is_err());
        assert!(parse_count(b"1\n2\n").is_err());
        assert!(parse_count(b"-1\n").is_err());
        assert!(parse_count(b"18446744073709551616\n").is_err());
    }

    #[tokio::test]
    async fn runner_receives_count_and_kind_one_filter() {
        let path = runner(
            "[ \"$1\" = scan ]\n[ \"$2\" = --count ]\n[ \"$3\" = '{\"kinds\":[1]}' ]\nprintf '42\\n'",
        );
        assert_eq!(count_notes_with(&path).await.unwrap(), 42);
        fs::remove_file(path).unwrap();
    }

    #[tokio::test]
    async fn runner_failure_does_not_become_a_fake_zero() {
        let path = runner("echo unavailable >&2\nexit 7");
        let error = count_notes_with(&path).await.unwrap_err();
        assert!(error.contains("unavailable"));
        fs::remove_file(path).unwrap();
    }
}
