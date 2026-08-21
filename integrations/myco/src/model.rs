use std::fs;
use std::io::Write;
use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

pub const MAX_FILE_BYTES: usize = 64 * 1024 * 1024;
pub const MAX_TRACKED_TRANSFERS: usize = 64;
pub const OFFER_TTL_SECS: u64 = 10 * 60;
pub const PAIR_TTL_SECS: u64 = 7 * 24 * 60 * 60;
pub const INVITE_TTL_SECS: u64 = 30 * 60;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct Contact {
    pub npub: String,
    pub name: String,
    pub added_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PairRequest {
    pub npub: String,
    pub name: String,
    pub secret: String,
    pub authorized_invite: bool,
    pub received_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct OutboundPair {
    pub npub: String,
    pub name: String,
    pub expires_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct IssuedInvite {
    pub secret: String,
    pub expires_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct TransferView {
    pub id: String,
    pub direction: String,
    pub peer_npub: String,
    pub peer_name: String,
    pub name: String,
    pub mime: String,
    pub size: u64,
    pub status: String,
    pub blob_hash: String,
    pub received_path: String,
    pub error: String,
    pub updated_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TransferRecord {
    #[serde(flatten)]
    pub view: TransferView,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub key_b64: Option<String>,
    #[serde(default)]
    pub ciphertext_size: u64,
    pub expires_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PersistentState {
    pub device_name: String,
    #[serde(default)]
    pub circle: Vec<Contact>,
    #[serde(default)]
    pub pending_pairs: Vec<PairRequest>,
    #[serde(default)]
    pub outbound_pairs: Vec<OutboundPair>,
    #[serde(default)]
    pub issued_invites: Vec<IssuedInvite>,
    #[serde(default)]
    pub transfers: Vec<TransferRecord>,
}

impl Default for PersistentState {
    fn default() -> Self {
        Self {
            device_name: "Totem".to_string(),
            circle: Vec::new(),
            pending_pairs: Vec::new(),
            outbound_pairs: Vec::new(),
            issued_invites: Vec::new(),
            transfers: Vec::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicState {
    pub protocol: &'static str,
    pub npub: String,
    pub device_name: String,
    pub circle: Vec<Contact>,
    pub pending_pairs: Vec<PairRequest>,
    pub outbound_pairs: Vec<OutboundPair>,
    pub transfers: Vec<TransferView>,
}

pub struct StateStore {
    path: PathBuf,
    inner: Mutex<PersistentState>,
}

impl StateStore {
    pub fn open(data_dir: &Path, default_name: &str) -> Result<Self> {
        fs::create_dir_all(data_dir)
            .with_context(|| format!("create state directory {}", data_dir.display()))?;
        fs::set_permissions(data_dir, fs::Permissions::from_mode(0o700))?;
        let path = data_dir.join("state.json");
        let mut state = match fs::read(&path) {
            Ok(bytes) => serde_json::from_slice(&bytes)
                .with_context(|| format!("parse {}", path.display()))?,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => PersistentState::default(),
            Err(e) => return Err(e).with_context(|| format!("read {}", path.display())),
        };
        if state.device_name == "Totem" && !default_name.trim().is_empty() {
            state.device_name = default_name.trim().to_string();
        }
        let store = Self {
            path,
            inner: Mutex::new(state),
        };
        store.save()?;
        Ok(store)
    }

    pub fn snapshot(&self) -> PersistentState {
        self.inner.lock().expect("state lock").clone()
    }

    pub fn update<T>(&self, f: impl FnOnce(&mut PersistentState) -> T) -> Result<T> {
        let mut state = self.inner.lock().expect("state lock");
        let result = f(&mut state);
        self.write(&state)?;
        Ok(result)
    }

    pub fn public(&self, npub: String) -> PublicState {
        let state = self.snapshot();
        PublicState {
            protocol: "myco/852bcda",
            npub,
            device_name: state.device_name,
            circle: state.circle,
            pending_pairs: state.pending_pairs,
            outbound_pairs: state.outbound_pairs,
            transfers: state.transfers.into_iter().map(|r| r.view).collect(),
        }
    }

    pub fn save(&self) -> Result<()> {
        let state = self.inner.lock().expect("state lock");
        self.write(&state)
    }

    fn write(&self, state: &PersistentState) -> Result<()> {
        let tmp = self.path.with_extension("json.tmp");
        let bytes = serde_json::to_vec_pretty(state)?;
        let mut file = fs::OpenOptions::new()
            .create(true)
            .truncate(true)
            .write(true)
            .mode(0o600)
            .open(&tmp)
            .with_context(|| format!("open {}", tmp.display()))?;
        file.write_all(&bytes)?;
        file.write_all(b"\n")?;
        file.sync_all()?;
        fs::set_permissions(&tmp, fs::Permissions::from_mode(0o600))?;
        fs::rename(&tmp, &self.path)?;
        Ok(())
    }
}

pub fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

pub fn short_name(npub: &str) -> String {
    format!(
        "Myco-{}",
        npub.strip_prefix("npub1")
            .unwrap_or(npub)
            .chars()
            .take(6)
            .collect::<String>()
    )
}
