//! Durable owner claim and owner-controlled policy overrides.

use std::{
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::OpenOptionsExt,
    path::{Path, PathBuf},
    sync::Mutex,
};

use nostr::prelude::PublicKey;

use crate::config::{Befriend, Config};

const VERSION: u8 = 1;
const STATE_PATH: &str = "/var/lib/totemd/state.toml";

#[derive(Clone, Debug, serde::Deserialize, serde::Serialize)]
#[serde(deny_unknown_fields)]
struct Persisted {
    version: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    owner: Option<String>,
    #[serde(default)]
    policy: Policy,
}

impl Default for Persisted {
    fn default() -> Self {
        Self {
            version: VERSION,
            owner: None,
            policy: Policy::default(),
        }
    }
}

#[derive(Clone, Debug, Default, serde::Deserialize, serde::Serialize)]
#[serde(deny_unknown_fields)]
struct Policy {
    #[serde(skip_serializing_if = "Option::is_none")]
    befriend: Option<Befriend>,
    #[serde(skip_serializing_if = "Option::is_none")]
    sync: Option<bool>,
}

pub struct Store {
    base: Config,
    path: Option<PathBuf>,
    data: Mutex<Persisted>,
}

impl Store {
    #[cfg(test)]
    pub fn memory(base: Config) -> Self {
        Self {
            base,
            path: None,
            data: Mutex::new(Persisted::default()),
        }
    }

    pub fn load(base: Config, path: PathBuf) -> Result<Self, String> {
        let data = match fs::read_to_string(&path) {
            Ok(value) => toml::from_str(&value)
                .map_err(|e| format!("parse owner state {}: {e}", path.display()))?,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Persisted::default(),
            Err(e) => return Err(format!("read owner state {}: {e}", path.display())),
        };
        validate(&data)?;
        Ok(Self {
            base,
            path: Some(path),
            data: Mutex::new(data),
        })
    }

    pub fn effective_config(&self) -> Config {
        let data = self.data.lock().unwrap();
        let mut config = self.base.clone();
        if let Some(value) = data.policy.befriend {
            config.befriend = value;
        }
        if let Some(value) = data.policy.sync {
            config.sync = value;
        }
        config
    }

    pub fn owner(&self) -> Option<PublicKey> {
        self.data
            .lock()
            .unwrap()
            .owner
            .as_deref()
            .map(|value| PublicKey::from_hex(value).expect("validated owner state"))
    }

    pub fn claim(&self, owner: PublicKey) -> Result<bool, String> {
        let mut current = self.data.lock().unwrap();
        if current.owner.is_some() {
            return Ok(false);
        }
        let mut next = current.clone();
        next.owner = Some(owner.to_hex());
        self.save(&next)?;
        *current = next;
        Ok(true)
    }

    pub fn update_policy(&self, sync: bool, befriend: Befriend) -> Result<Config, String> {
        let mut current = self.data.lock().unwrap();
        let mut next = current.clone();
        next.policy.sync = Some(sync);
        next.policy.befriend = Some(befriend);
        self.save(&next)?;
        *current = next;
        drop(current);
        Ok(self.effective_config())
    }

    fn save(&self, data: &Persisted) -> Result<(), String> {
        let Some(path) = &self.path else {
            return Ok(());
        };
        let value = toml::to_string(data).map_err(|e| format!("serialize owner state: {e}"))?;
        write_atomic(path, value.as_bytes())
    }
}

pub fn path() -> PathBuf {
    std::env::var_os("TOTEMD_STATE")
        .map(PathBuf::from)
        .unwrap_or_else(|| STATE_PATH.into())
}

fn validate(data: &Persisted) -> Result<(), String> {
    if data.version != VERSION {
        return Err(format!(
            "owner state version {} is unsupported (want {VERSION})",
            data.version
        ));
    }
    if let Some(owner) = &data.owner {
        PublicKey::from_hex(owner).map_err(|e| format!("owner state pubkey: {e}"))?;
    }
    Ok(())
}

fn write_atomic(path: &Path, value: &[u8]) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| format!("{} has no parent", path.display()))?;
    fs::create_dir_all(parent).map_err(|e| format!("create {}: {e}", parent.display()))?;
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| format!("invalid state path: {}", path.display()))?;
    let temporary = parent.join(format!(".{name}.{}.tmp", std::process::id()));
    let result = (|| {
        let mut file = OpenOptions::new()
            .create(true)
            .truncate(true)
            .write(true)
            .mode(0o600)
            .open(&temporary)
            .map_err(|e| format!("write {}: {e}", temporary.display()))?;
        file.write_all(value)
            .map_err(|e| format!("write {}: {e}", temporary.display()))?;
        file.sync_all()
            .map_err(|e| format!("sync {}: {e}", temporary.display()))?;
        fs::rename(&temporary, path).map_err(|e| format!("replace {}: {e}", path.display()))?;
        fs::File::open(parent)
            .and_then(|dir| dir.sync_all())
            .map_err(|e| format!("sync {}: {e}", parent.display()))
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        os::unix::fs::PermissionsExt,
        sync::atomic::{AtomicUsize, Ordering},
    };

    static NEXT: AtomicUsize = AtomicUsize::new(0);

    fn state_path() -> PathBuf {
        std::env::temp_dir().join(format!(
            "totemd-owner-test-{}-{}.toml",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ))
    }

    fn key(n: u8) -> PublicKey {
        nostr::prelude::Keys::parse(&format!("{n:064x}"))
            .unwrap()
            .public_key()
    }

    #[test]
    fn claim_and_policy_survive_reload() {
        let path = state_path();
        let store = Store::load(Config::default(), path.clone()).unwrap();
        assert!(store.owner().is_none());
        assert!(store.claim(key(1)).unwrap());
        assert!(!store.claim(key(2)).unwrap());
        let config = store.update_policy(false, Befriend::Never).unwrap();
        assert!(!config.sync);
        assert_eq!(config.befriend, Befriend::Never);
        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );

        let reloaded = Store::load(Config::default(), path.clone()).unwrap();
        assert_eq!(reloaded.owner(), Some(key(1)));
        assert!(!reloaded.effective_config().sync);
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn corrupt_or_unknown_state_is_not_unclaimed() {
        let path = state_path();
        fs::write(&path, "version = 99\n").unwrap();
        assert!(Store::load(Config::default(), path.clone()).is_err());
        fs::write(&path, "not = [valid").unwrap();
        assert!(Store::load(Config::default(), path.clone()).is_err());
        fs::remove_file(path).unwrap();
    }
}
