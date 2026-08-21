//! Durable append-only history of successful signed peer recognitions.
//!
//! This is deliberately separate from the current-encounter recognition set:
//! history answers whether a peer was known before an encounter, while every
//! encounter must still pass its own signed challenge.

use std::{
    collections::HashSet,
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
    sync::Mutex,
};

use nostr::{nips::nip19::FromBech32, prelude::PublicKey};

const VERSION: u8 = 1;
const HISTORY_PATH: &str = "/var/lib/totemd/recognized-encounters.jsonl";

#[derive(Debug, serde::Serialize)]
struct Record<'a> {
    version: u8,
    npub: &'a str,
    encounter: u64,
}

#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct OwnedRecord {
    version: u8,
    npub: String,
    encounter: u64,
}

pub struct Store {
    path: Option<PathBuf>,
    known: Mutex<HashSet<String>>,
}

impl Store {
    #[cfg(test)]
    pub fn memory() -> Self {
        Self {
            path: None,
            known: Mutex::new(HashSet::new()),
        }
    }

    pub fn load(path: PathBuf) -> Result<Self, String> {
        let known = load_known(&path)?;
        Ok(Self {
            path: Some(path),
            known: Mutex::new(known),
        })
    }

    /// Persist one successful encounter and return whether this identity was
    /// already present before the append. In-memory state advances only after
    /// the record and its directory entry have been synced successfully.
    pub fn record(&self, npub: &str, encounter: u64) -> Result<bool, String> {
        if self.path.is_some() && !valid_npub(npub) {
            return Err("record encounter history: invalid npub".into());
        }
        let mut known = self.known.lock().unwrap();
        let known_before = known.contains(npub);
        if let Some(path) = &self.path {
            append(path, npub, encounter)?;
        }
        known.insert(npub.to_owned());
        Ok(known_before)
    }

    pub fn contains(&self, npub: &str) -> bool {
        self.known.lock().unwrap().contains(npub)
    }
}

pub fn path() -> PathBuf {
    std::env::var_os("TOTEMD_ENCOUNTER_HISTORY")
        .map(PathBuf::from)
        .unwrap_or_else(|| HISTORY_PATH.into())
}

fn load_known(path: &Path) -> Result<HashSet<String>, String> {
    let mut file = match OpenOptions::new().read(true).write(true).open(path) {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(HashSet::new()),
        Err(e) => return Err(format!("read encounter history {}: {e}", path.display())),
    };
    file.set_permissions(fs::Permissions::from_mode(0o600))
        .map_err(|e| format!("secure encounter history {}: {e}", path.display()))?;
    file.sync_all()
        .map_err(|e| format!("sync encounter history {}: {e}", path.display()))?;
    let mut known = HashSet::new();
    let mut reader = BufReader::new(&mut file);
    let mut line = String::new();
    let mut line_number = 0usize;
    let mut valid_bytes = 0u64;
    loop {
        line.clear();
        let bytes = reader
            .read_line(&mut line)
            .map_err(|e| format!("read encounter history {}: {e}", path.display()))?;
        if bytes == 0 {
            break;
        }
        line_number += 1;
        if !line.ends_with('\n') {
            // One torn final append has no commit newline and therefore never
            // became an accepted encounter. Drop only that tail; completed
            // records remain strict and any corruption in them still fails
            // startup closed.
            drop(reader);
            file.set_len(valid_bytes).map_err(|e| {
                format!(
                    "repair encounter history {} line {line_number}: {e}",
                    path.display()
                )
            })?;
            file.sync_all()
                .map_err(|e| format!("sync encounter history {}: {e}", path.display()))?;
            sync_parent(path)?;
            return Ok(known);
        }
        let record: OwnedRecord = serde_json::from_str(line.trim_end_matches(['\r', '\n']))
            .map_err(|e| {
                format!(
                    "parse encounter history {} line {line_number}: {e}",
                    path.display()
                )
            })?;
        validate(&record, path, line_number)?;
        known.insert(record.npub);
        valid_bytes += bytes as u64;
    }
    Ok(known)
}

fn validate(record: &OwnedRecord, path: &Path, line_number: usize) -> Result<(), String> {
    if record.version != VERSION {
        return Err(format!(
            "encounter history {} line {line_number} version {} is unsupported (want {VERSION})",
            path.display(),
            record.version
        ));
    }
    if !valid_npub(&record.npub) {
        return Err(format!(
            "encounter history {} line {line_number} has an invalid npub",
            path.display()
        ));
    }
    // Read the field even though the timestamp-like encounter token is not a
    // freshness authority and zero is valid on clocks without a sane epoch.
    let _ = record.encounter;
    Ok(())
}

fn valid_npub(npub: &str) -> bool {
    npub.starts_with("npub1") && PublicKey::from_bech32(npub).is_ok()
}

fn append(path: &Path, npub: &str, encounter: u64) -> Result<(), String> {
    append_with_sync(path, npub, encounter, |file| file.sync_all())
}

fn append_with_sync<F>(path: &Path, npub: &str, encounter: u64, sync_file: F) -> Result<(), String>
where
    F: FnOnce(&mut fs::File) -> std::io::Result<()>,
{
    let parent = path
        .parent()
        .ok_or_else(|| format!("{} has no parent", path.display()))?;
    fs::create_dir_all(parent).map_err(|e| format!("create {}: {e}", parent.display()))?;
    let mut value = serde_json::to_vec(&Record {
        version: VERSION,
        npub,
        encounter,
    })
    .map_err(|e| format!("serialize encounter history: {e}"))?;
    value.push(b'\n');

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .read(true)
        .mode(0o600)
        .open(path)
        .map_err(|e| format!("append encounter history {}: {e}", path.display()))?;
    file.set_permissions(fs::Permissions::from_mode(0o600))
        .map_err(|e| format!("secure encounter history {}: {e}", path.display()))?;
    let original_len = file
        .metadata()
        .map_err(|e| format!("inspect encounter history {}: {e}", path.display()))?
        .len();
    let result = (|| {
        file.write_all(&value)
            .map_err(|e| format!("append encounter history {}: {e}", path.display()))?;
        sync_file(&mut file)
            .map_err(|e| format!("sync encounter history {}: {e}", path.display()))?;
        sync_parent(path)
    })();
    if let Err(error) = result {
        let rollback = file
            .set_len(original_len)
            .and_then(|()| file.sync_all())
            .map_err(|e| format!("roll back encounter history {}: {e}", path.display()))
            .and_then(|()| sync_parent(path));
        return match rollback {
            Ok(()) => Err(error),
            Err(rollback_error) => Err(format!("{error}; {rollback_error}")),
        };
    }
    Ok(())
}

fn sync_parent(path: &Path) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| format!("{} has no parent", path.display()))?;
    fs::File::open(parent)
        .and_then(|dir| dir.sync_all())
        .map_err(|e| format!("sync {}: {e}", parent.display()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        os::unix::fs::PermissionsExt,
        sync::atomic::{AtomicUsize, Ordering},
    };

    static NEXT: AtomicUsize = AtomicUsize::new(0);
    const FIRST_NPUB: &str = "npub1eu0clm0nsxwavcsj07at3sy7v52tuwgw4qpeqsyxgkeqg7krc7ps77c20q";
    const SECOND_NPUB: &str = "npub1j0adney3t3tuvcaz6wv6eahpkhfrl8rwhry58n2u4njuxz0j04lsrudpf6";

    fn history_path() -> PathBuf {
        std::env::temp_dir().join(format!(
            "totemd-encounter-test-{}-{}.jsonl",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ))
    }

    #[test]
    fn append_only_records_survive_restart() {
        let path = history_path();
        let store = Store::load(path.clone()).unwrap();
        assert!(!store.contains(FIRST_NPUB));
        assert!(!store.record(FIRST_NPUB, 10).unwrap());
        assert!(store.record(FIRST_NPUB, 20).unwrap());
        assert!(!store.record(SECOND_NPUB, 30).unwrap());
        assert_eq!(fs::read_to_string(&path).unwrap().lines().count(), 3);
        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );

        let reloaded = Store::load(path.clone()).unwrap();
        assert!(reloaded.contains(FIRST_NPUB));
        assert!(reloaded.contains(SECOND_NPUB));
        assert!(reloaded.record(FIRST_NPUB, 40).unwrap());
        assert_eq!(fs::read_to_string(&path).unwrap().lines().count(), 4);
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn corrupt_or_unknown_completed_records_fail_closed() {
        for value in [
            "not json\n".to_owned(),
            format!("{{\"version\":2,\"npub\":\"{FIRST_NPUB}\",\"encounter\":1}}\n"),
            format!("{{\"version\":1,\"npub\":\"{FIRST_NPUB}\",\"encounter\":1,\"extra\":true}}\n"),
            "{\"version\":1,\"npub\":\"not-an-npub\",\"encounter\":1}\n".to_owned(),
        ] {
            let path = history_path();
            fs::write(&path, &value).unwrap();
            assert!(Store::load(path.clone()).is_err(), "accepted {value:?}");
            fs::remove_file(path).unwrap();
        }
    }

    #[test]
    fn torn_final_append_is_removed_without_losing_completed_records() {
        let path = history_path();
        let complete = format!("{{\"version\":1,\"npub\":\"{FIRST_NPUB}\",\"encounter\":1}}\n");
        fs::write(
            &path,
            format!("{complete}{{\"version\":1,\"npub\":\"{SECOND_NPUB}"),
        )
        .unwrap();

        let store = Store::load(path.clone()).unwrap();

        assert!(store.contains(FIRST_NPUB));
        assert!(!store.contains(SECOND_NPUB));
        assert_eq!(fs::read_to_string(&path).unwrap(), complete);
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn existing_history_permissions_are_repaired() {
        let path = history_path();
        fs::write(
            &path,
            format!("{{\"version\":1,\"npub\":\"{FIRST_NPUB}\",\"encounter\":1}}\n"),
        )
        .unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o644)).unwrap();

        Store::load(path.clone()).unwrap();

        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn post_write_failure_rolls_back_to_the_previous_complete_record() {
        let path = history_path();
        let store = Store::load(path.clone()).unwrap();
        assert!(!store.record(FIRST_NPUB, 10).unwrap());
        let original = fs::read(&path).unwrap();

        let error = append_with_sync(&path, SECOND_NPUB, 20, |_| {
            Err(std::io::Error::other("injected sync failure"))
        })
        .unwrap_err();

        assert!(error.contains("injected sync failure"));
        assert_eq!(fs::read(&path).unwrap(), original);
        let reloaded = Store::load(path.clone()).unwrap();
        assert!(reloaded.contains(FIRST_NPUB));
        assert!(!reloaded.contains(SECOND_NPUB));
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn unreadable_history_path_fails_closed() {
        let path = history_path();
        fs::create_dir(&path).unwrap();
        assert!(Store::load(path.clone()).is_err());
        fs::remove_dir(path).unwrap();
    }
}
