use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use anyhow::{bail, Context, Result};
use futures_util::{SinkExt, StreamExt};
use nostr::prelude::*;
use tokio_tungstenite::tungstenite::Message;
use zeroize::Zeroizing;

use crate::model::{
    now_secs, short_name, Contact, IssuedInvite, OutboundPair, PairRequest, StateStore,
    TransferRecord, TransferView, INVITE_TTL_SECS, MAX_TRACKED_TRANSFERS, OFFER_TTL_SECS,
};
use crate::protocol::{self, FileMessage, PairPayload};
use crate::transport::{
    AwarePeerIdentity, L2capConnection, L2capListener, NanDataPath, NanDiscovery, NanMatch,
    PeerLane, TransportKind, TransportManager, TransportStatus,
};

pub struct App {
    keys: Keys,
    store: StateStore,
    data_dir: PathBuf,
    blobs_dir: PathBuf,
    received_dir: PathBuf,
    outbox_dir: PathBuf,
    client: reqwest::Client,
    transport: TransportManager,
    aware_tasks: Mutex<HashMap<String, tokio::task::JoinHandle<()>>>,
}

impl App {
    pub fn open(data_dir: &Path, credential: &Path, name: &str) -> Result<Arc<Self>> {
        let secret = Zeroizing::new(
            std::fs::read_to_string(credential)
                .with_context(|| format!("read identity credential {}", credential.display()))?,
        );
        let keys = Keys::parse(secret.trim()).context("parse FIPS identity credential")?;
        let store = StateStore::open(data_dir, name)?;
        let blobs_dir = data_dir.join("blobs");
        let received_dir = data_dir.join("received");
        let outbox_dir = data_dir.join("outbox");
        for dir in [&blobs_dir, &received_dir, &outbox_dir] {
            std::fs::create_dir_all(dir)?;
        }
        let client = reqwest::Client::builder()
            .connect_timeout(Duration::from_secs(15))
            .timeout(Duration::from_secs(120))
            .build()?;
        let device_manager_url = std::env::var("TOTEM_DEVICE_MANAGER_URL")
            .unwrap_or_else(|_| "http://127.0.0.1:8000".into());
        Ok(Arc::new(Self {
            keys,
            store,
            data_dir: data_dir.to_path_buf(),
            blobs_dir,
            received_dir,
            outbox_dir,
            client,
            transport: TransportManager::new(device_manager_url)?,
            aware_tasks: Mutex::new(HashMap::new()),
        }))
    }

    pub fn npub(&self) -> String {
        self.keys
            .public_key()
            .to_bech32()
            .expect("public key encodes as npub")
    }

    pub fn public_state(&self) -> crate::model::PublicState {
        self.store.public(self.npub())
    }

    pub fn data_dir(&self) -> &Path {
        &self.data_dir
    }

    pub fn is_in_circle(&self, npub: &str) -> bool {
        self.store.snapshot().circle.iter().any(|p| p.npub == npub)
    }

    pub fn circle_npub_for_ip(&self, ip: std::net::Ipv6Addr) -> Option<String> {
        let state = self.store.snapshot();
        protocol::npub_for_ipv6(state.circle.iter().map(|p| p.npub.as_str()), ip)
    }

    pub async fn transport_status(&self) -> TransportStatus {
        self.transport.status().await
    }

    pub async fn connect_udp_lane(
        &self,
        npub: &str,
        address: &str,
        kind: &str,
    ) -> Result<PeerLane> {
        self.transport
            .connect_udp_lane(npub, address, TransportKind::udp_lane(kind)?)
            .await
    }

    pub fn remove_udp_lane(&self, npub: &str, kind: &str) -> Result<()> {
        self.transport
            .remove_udp_lane(npub, TransportKind::udp_lane(kind)?);
        Ok(())
    }

    pub async fn start_aware_discovery(
        &self,
        udp_port: u16,
        duration: u16,
    ) -> Result<NanDiscovery> {
        self.transport
            .start_aware_discovery(udp_port, duration)
            .await
    }

    pub fn maintain_aware_identity(
        self: &Arc<Self>,
        session: &NanDiscovery,
        udp_port: u16,
        duration: u16,
    ) {
        let session_id = session.id.clone();
        let app = Arc::clone(self);
        let task_session_id = session_id.clone();
        let task = tokio::spawn(async move {
            let deadline = tokio::time::Instant::now() + Duration::from_secs(duration.into());
            loop {
                if tokio::time::Instant::now() >= deadline {
                    break;
                }
                if let Err(error) = app
                    .exchange_aware_identity(&task_session_id, udp_port)
                    .await
                {
                    tracing::warn!(
                        session_id = %task_session_id,
                        error = %error,
                        "Wi-Fi Aware identity exchange attempt failed"
                    );
                }
                let now = tokio::time::Instant::now();
                let remaining = deadline.saturating_duration_since(now);
                tokio::time::sleep(remaining.min(Duration::from_secs(1))).await;
            }
            app.aware_tasks
                .lock()
                .expect("Aware task lock poisoned")
                .remove(&task_session_id);
        });
        if let Some(previous) = self
            .aware_tasks
            .lock()
            .expect("Aware task lock poisoned")
            .insert(session_id, task)
        {
            previous.abort();
        }
    }

    pub async fn exchange_aware_identity(
        &self,
        session_id: &str,
        udp_port: u16,
    ) -> Result<Vec<AwarePeerIdentity>> {
        self.transport
            .exchange_aware_identity(session_id, &self.npub(), udp_port)
            .await
    }

    pub fn aware_identities(&self) -> Vec<AwarePeerIdentity> {
        self.transport.aware_identities()
    }

    pub fn aware_identity(&self, match_id: &str) -> Option<AwarePeerIdentity> {
        self.transport.aware_identity(match_id)
    }

    pub async fn create_aware_path(
        &self,
        npub: &str,
        match_id: &str,
        port: u16,
    ) -> Result<NanDataPath> {
        self.transport.create_aware_path(npub, match_id, port).await
    }

    pub async fn aware_matches(&self) -> Result<Vec<NanMatch>> {
        self.transport.aware_matches().await
    }

    pub async fn stop_aware_discovery(&self, session_id: &str) -> Result<()> {
        if let Some(task) = self
            .aware_tasks
            .lock()
            .expect("Aware task lock poisoned")
            .remove(session_id)
        {
            task.abort();
        }
        self.transport.stop_aware_discovery(session_id).await
    }

    pub async fn remove_aware_path(&self, data_path_id: &str) -> Result<()> {
        self.transport.remove_aware_path(data_path_id).await
    }

    pub async fn connect_coc(
        &self,
        npub: &str,
        peer_address: &str,
        psm: u16,
        mtu: u16,
        address_type: &str,
    ) -> Result<L2capConnection> {
        self.transport
            .connect_coc(npub, peer_address, psm, mtu, address_type)
            .await
    }

    pub async fn create_coc_listener(
        &self,
        psm: u16,
        mtu: u16,
        address_type: &str,
    ) -> Result<L2capListener> {
        self.transport
            .create_coc_listener(psm, mtu, address_type)
            .await
    }

    pub async fn coc_listeners(&self) -> Result<Vec<L2capListener>> {
        self.transport.coc_listeners().await
    }

    pub async fn close_coc_listener(&self, listener_id: &str) -> Result<()> {
        self.transport.close_coc_listener(listener_id).await
    }

    pub async fn handoff_coc(&self, npub: &str, connection_id: &str) -> Result<serde_json::Value> {
        self.transport.handoff_coc(npub, connection_id).await
    }

    pub fn create_invite(&self) -> Result<String> {
        let secret = protocol::new_secret();
        let now = now_secs();
        let name = self.store.snapshot().device_name;
        self.store.update(|state| {
            state.issued_invites.retain(|i| i.expires_at > now);
            state.issued_invites.push(IssuedInvite {
                secret: secret.clone(),
                expires_at: now + INVITE_TTL_SECS,
            });
        })?;
        protocol::build_pair_uri(&PairPayload {
            v: 1,
            npub: self.npub(),
            name,
            secret,
        })
    }

    pub async fn pair_from_uri(&self, uri: &str) -> Result<()> {
        let pair = protocol::parse_pair_uri(uri)?;
        if pair.npub == self.npub() {
            bail!("cannot pair this Totem with itself");
        }
        if self.is_in_circle(&pair.npub) {
            return Ok(());
        }
        let now = now_secs();
        self.store.update(|state| {
            state.outbound_pairs.retain(|p| p.npub != pair.npub);
            state.outbound_pairs.push(OutboundPair {
                npub: pair.npub.clone(),
                name: pair.name.clone(),
                expires_at: now + crate::model::PAIR_TTL_SECS,
            });
        })?;
        self.post_pair_event(&pair.npub, protocol::KIND_PAIR_REQUEST, &pair.secret)
            .await
    }

    pub async fn accept_pair(&self, npub: &str) -> Result<()> {
        let request = self
            .store
            .snapshot()
            .pending_pairs
            .into_iter()
            .find(|p| p.npub == npub)
            .context("pair request not found")?;
        self.add_circle(&request.npub, &request.name)?;
        self.store
            .update(|state| state.pending_pairs.retain(|p| p.npub != npub))?;
        self.post_pair_event(npub, protocol::KIND_PAIR_ACCEPT, "")
            .await
    }

    pub fn decline_pair(&self, npub: &str) -> Result<()> {
        self.store
            .update(|state| state.pending_pairs.retain(|p| p.npub != npub))
    }

    pub async fn unpair(&self, npub: &str) -> Result<()> {
        self.store.update(|state| {
            state.circle.retain(|p| p.npub != npub);
            state.pending_pairs.retain(|p| p.npub != npub);
            state.outbound_pairs.retain(|p| p.npub != npub);
        })?;
        self.post_pair_event(npub, protocol::KIND_PAIR_REMOVE, "")
            .await
    }

    pub fn handle_pair_event(&self, event: &Event) -> Result<&'static str> {
        event.verify().context("bad event signature")?;
        if protocol::event_expired(event) {
            bail!("pair event expired");
        }
        if !protocol::addressed_to(event, &self.keys) {
            bail!("pair event addressed to another device");
        }
        let sender = event.pubkey.to_bech32()?;
        let name = protocol::tag_value(event, "n").unwrap_or_else(|| short_name(&sender));
        match event.kind.as_u16() {
            protocol::KIND_PAIR_REQUEST => {
                let secret = protocol::tag_value(event, "secret").unwrap_or_default();
                let now = now_secs();
                self.store.update(|state| {
                    state.issued_invites.retain(|i| i.expires_at > now);
                    let authorized = state
                        .issued_invites
                        .iter()
                        .any(|i| i.secret == secret && i.expires_at > now);
                    if authorized {
                        state.issued_invites.retain(|i| i.secret != secret);
                    }
                    state.pending_pairs.retain(|p| p.npub != sender);
                    state.pending_pairs.push(PairRequest {
                        npub: sender.clone(),
                        name,
                        secret,
                        authorized_invite: authorized,
                        received_at: now,
                    });
                })?;
                Ok("pending")
            }
            protocol::KIND_PAIR_ACCEPT => {
                let invited = self
                    .store
                    .snapshot()
                    .outbound_pairs
                    .iter()
                    .any(|p| p.npub == sender && p.expires_at > now_secs());
                if !invited {
                    bail!("accept does not answer an outstanding invite");
                }
                self.add_circle(&sender, &name)?;
                Ok("paired")
            }
            protocol::KIND_PAIR_REMOVE => {
                self.store.update(|state| {
                    state.circle.retain(|p| p.npub != sender);
                    state.pending_pairs.retain(|p| p.npub != sender);
                    state.outbound_pairs.retain(|p| p.npub != sender);
                })?;
                Ok("unpaired")
            }
            _ => bail!("not a Myco pairing event"),
        }
    }

    fn add_circle(&self, npub: &str, name: &str) -> Result<()> {
        let now = now_secs();
        self.store.update(|state| {
            state.outbound_pairs.retain(|p| p.npub != npub);
            if let Some(contact) = state.circle.iter_mut().find(|p| p.npub == npub) {
                if !name.is_empty() {
                    contact.name = name.to_string();
                }
            } else {
                state.circle.push(Contact {
                    npub: npub.to_string(),
                    name: if name.is_empty() {
                        short_name(npub)
                    } else {
                        name.to_string()
                    },
                    added_at: now,
                });
            }
        })
    }

    async fn post_pair_event(&self, npub: &str, kind: u16, secret: &str) -> Result<()> {
        let name = self.store.snapshot().device_name;
        let event = protocol::pair_event(&self.keys, kind, npub, &name, secret)?;
        let ip = protocol::peer_ipv6(npub)?;
        let url = format!("http://[{ip}]:4873/pair");
        let response = self
            .client
            .post(url)
            .body(serde_json::to_vec(&event)?)
            .send()
            .await?;
        if !response.status().is_success() {
            bail!("peer pairing service returned {}", response.status());
        }
        Ok(())
    }

    pub async fn share_file(
        self: &Arc<Self>,
        path: &Path,
        target_npub: &str,
        display_name: Option<&str>,
        mime: Option<&str>,
    ) -> Result<String> {
        if !self.is_in_circle(target_npub) {
            bail!("file share target is not in the Circle");
        }
        let plain = tokio::fs::read(path).await?;
        if plain.len() > crate::model::MAX_FILE_BYTES {
            bail!("file is larger than the 64 MiB Myco limit");
        }
        let filename = protocol::safe_filename(
            display_name.unwrap_or_else(|| {
                path.file_name()
                    .and_then(|v| v.to_str())
                    .unwrap_or("shared-file")
            }),
            "shared-file",
        );
        let mime = mime.unwrap_or("application/octet-stream").to_string();
        if let Some(reason) = protocol::rejected_payload(&filename, &mime) {
            bail!(reason);
        }
        let id = protocol::new_transfer_id();
        let (package, key) = protocol::encrypt_file(&plain, &id, target_npub, &filename)?;
        let outbox = self.outbox_dir.join(format!("{id}.bin"));
        tokio::fs::write(&outbox, &package).await?;
        let now = now_secs();
        let peer_name = self.peer_name(target_npub);
        self.store.update(|state| {
            prune_transfers(&mut state.transfers);
            state.transfers.push(TransferRecord {
                view: TransferView {
                    id: id.clone(),
                    direction: "outgoing".into(),
                    peer_npub: target_npub.to_string(),
                    peer_name,
                    name: filename.clone(),
                    mime: mime.clone(),
                    size: plain.len() as u64,
                    status: "offered".into(),
                    blob_hash: String::new(),
                    received_path: String::new(),
                    error: String::new(),
                    updated_at: now,
                },
                source_path: Some(outbox.to_string_lossy().into_owned()),
                key_b64: Some(protocol::encode_key(&key)),
                ciphertext_size: package.len() as u64,
                expires_at: now + OFFER_TTL_SECS,
            });
        })?;
        let message = FileMessage::Offer {
            transfer_id: id.clone(),
            sender_npub: self.npub(),
            recipient_npub: target_npub.to_string(),
            filename,
            mime,
            size: plain.len() as u64,
            issued_at: now,
            expires_at: now + OFFER_TTL_SECS,
        };
        if let Err(error) = self.send_file_message(target_npub, &message).await {
            self.set_transfer_status(&id, "failed", &error.to_string())?;
            return Err(error);
        }
        Ok(id)
    }

    pub async fn respond_file(self: &Arc<Self>, id: &str, accepted: bool) -> Result<()> {
        let record = self
            .store
            .snapshot()
            .transfers
            .into_iter()
            .find(|r| r.view.id == id && r.view.direction == "incoming")
            .context("incoming file offer not found")?;
        if record.view.status != "waiting_user" {
            bail!("file offer is no longer waiting for a response");
        }
        self.set_transfer_status(id, if accepted { "accepted" } else { "denied" }, "")?;
        let message = FileMessage::Response {
            transfer_id: id.to_string(),
            sender_npub: self.npub(),
            recipient_npub: record.view.peer_npub.clone(),
            accepted,
            reason: (!accepted).then(|| "declined by recipient".to_string()),
        };
        self.send_file_message(&record.view.peer_npub, &message)
            .await
    }

    pub async fn handle_file_event(self: &Arc<Self>, event: Event) -> Result<()> {
        let (sender_key, message) = protocol::extract_file_message(&self.keys, &event).await?;
        if !protocol::valid_transfer_id(message.transfer_id()) {
            bail!("malformed transfer id");
        }
        let sender_npub = sender_key.to_bech32()?;
        if !self.is_in_circle(&sender_npub) {
            bail!("file message sender is not in the Circle");
        }
        let own_npub = self.npub();
        match message {
            FileMessage::Offer {
                transfer_id,
                recipient_npub,
                filename,
                mime,
                size,
                expires_at,
                ..
            } if recipient_npub == own_npub => {
                if expires_at <= now_secs() || size > crate::model::MAX_FILE_BYTES as u64 {
                    bail!("expired or oversized file offer");
                }
                let filename = protocol::safe_filename(&filename, "shared-file");
                if let Some(reason) = protocol::rejected_payload(&filename, &mime) {
                    bail!(reason);
                }
                let peer_name = self.peer_name(&sender_npub);
                self.store.update(|state| {
                    if state.transfers.iter().any(|r| r.view.id == transfer_id) {
                        return;
                    }
                    prune_transfers(&mut state.transfers);
                    if state.transfers.len() >= MAX_TRACKED_TRANSFERS {
                        return;
                    }
                    state.transfers.push(TransferRecord {
                        view: TransferView {
                            id: transfer_id,
                            direction: "incoming".into(),
                            peer_npub: sender_npub,
                            peer_name,
                            name: filename,
                            mime,
                            size,
                            status: "waiting_user".into(),
                            blob_hash: String::new(),
                            received_path: String::new(),
                            error: String::new(),
                            updated_at: now_secs(),
                        },
                        source_path: None,
                        key_b64: None,
                        ciphertext_size: 0,
                        expires_at,
                    });
                })?;
            }
            FileMessage::Response {
                transfer_id,
                recipient_npub,
                accepted,
                reason,
                ..
            } if recipient_npub == own_npub => {
                if !accepted {
                    self.set_transfer_status(
                        &transfer_id,
                        "denied",
                        reason.as_deref().unwrap_or("declined by recipient"),
                    )?;
                } else if self.transfer_in_state(&transfer_id, "outgoing", &sender_npub, "offered")
                {
                    self.set_transfer_status(&transfer_id, "accepted", "")?;
                    let app = Arc::clone(self);
                    tokio::spawn(async move {
                        if let Err(e) = app.finish_outgoing(&transfer_id).await {
                            let _ = app.set_transfer_status(&transfer_id, "failed", &e.to_string());
                        }
                    });
                }
            }
            FileMessage::Ready {
                transfer_id,
                recipient_npub,
                filename,
                mime,
                size,
                blob_hash,
                ciphertext_size,
                key_wrap,
                ..
            } if recipient_npub == own_npub => {
                if !self.transfer_in_state(&transfer_id, "incoming", &sender_npub, "accepted") {
                    bail!("file ready arrived before acceptance");
                }
                if !protocol::valid_blob_hash(&blob_hash)
                    || ciphertext_size > protocol::MAX_PACKAGE_BYTES
                {
                    bail!("invalid encrypted blob metadata");
                }
                let expected = self
                    .store
                    .snapshot()
                    .transfers
                    .into_iter()
                    .find(|r| r.view.id == transfer_id)
                    .context("transfer disappeared")?;
                if expected.view.name != protocol::safe_filename(&filename, "shared-file")
                    || expected.view.mime != mime
                    || expected.view.size != size
                {
                    bail!("ready message contradicts accepted offer");
                }
                let key = protocol::unwrap_key(&self.keys, &sender_key, &key_wrap)?;
                self.store.update(|state| {
                    if let Some(record) = state
                        .transfers
                        .iter_mut()
                        .find(|r| r.view.id == transfer_id)
                    {
                        record.view.status = "downloading".into();
                        record.view.blob_hash = blob_hash;
                        record.view.updated_at = now_secs();
                        record.key_b64 = Some(protocol::encode_key(&key));
                        record.ciphertext_size = ciphertext_size;
                    }
                })?;
                let app = Arc::clone(self);
                tokio::spawn(async move {
                    if let Err(e) = app.finish_incoming(&transfer_id, &sender_npub).await {
                        let _ = app.set_transfer_status(&transfer_id, "failed", &e.to_string());
                    }
                });
            }
            FileMessage::Complete {
                transfer_id,
                recipient_npub,
                ..
            } if recipient_npub == own_npub => {
                if self.transfer_in_state(&transfer_id, "outgoing", &sender_npub, "ready") {
                    self.set_transfer_status(&transfer_id, "completed", "")?;
                    self.cleanup_transfer_secrets(&transfer_id)?;
                }
            }
            _ => {}
        }
        Ok(())
    }

    async fn finish_outgoing(self: &Arc<Self>, id: &str) -> Result<()> {
        let record = self.transfer(id, "outgoing")?;
        let source = record
            .source_path
            .as_deref()
            .context("outbox path missing")?;
        let package = tokio::fs::read(source).await?;
        let blob_hash = protocol::sha256_hex(&package);
        tokio::fs::write(self.blobs_dir.join(&blob_hash), &package).await?;
        let key = protocol::decode_key(record.key_b64.as_deref().context("file key missing")?)?;
        let target = PublicKey::from_bech32(&record.view.peer_npub)?;
        let key_wrap = protocol::wrap_key(&self.keys, &target, &key)?;
        let message = FileMessage::Ready {
            transfer_id: id.to_string(),
            sender_npub: self.npub(),
            recipient_npub: record.view.peer_npub.clone(),
            filename: record.view.name.clone(),
            mime: record.view.mime.clone(),
            size: record.view.size,
            blob_hash: blob_hash.clone(),
            ciphertext_size: package.len() as u64,
            key_wrap,
        };
        self.send_file_message(&record.view.peer_npub, &message)
            .await?;
        self.store.update(|state| {
            if let Some(r) = state.transfers.iter_mut().find(|r| r.view.id == id) {
                r.view.status = "ready".into();
                r.view.blob_hash = blob_hash;
                r.view.updated_at = now_secs();
            }
        })?;
        Ok(())
    }

    async fn finish_incoming(self: &Arc<Self>, id: &str, sender_npub: &str) -> Result<()> {
        let record = self.transfer(id, "incoming")?;
        let limit = record.ciphertext_size.min(protocol::MAX_PACKAGE_BYTES);
        if limit == 0 {
            bail!("sender did not declare encrypted file size");
        }
        let ip = protocol::peer_ipv6(sender_npub)?;
        let url = format!("http://[{ip}]:24243/{}", record.view.blob_hash);
        let mut response = self.client.get(url).send().await?;
        if !response.status().is_success() {
            bail!("peer Blossom returned {}", response.status());
        }
        if response.content_length().is_some_and(|n| n > limit) {
            bail!("peer Blossom response exceeds declared size");
        }
        let mut package = Vec::with_capacity(limit.min(1024 * 1024) as usize);
        while let Some(chunk) = response.chunk().await? {
            if package.len() as u64 + chunk.len() as u64 > limit {
                bail!("peer sent more encrypted data than declared");
            }
            package.extend_from_slice(&chunk);
        }
        if protocol::sha256_hex(&package) != record.view.blob_hash {
            bail!("downloaded encrypted blob hash mismatch");
        }
        let key = protocol::decode_key(record.key_b64.as_deref().context("file key missing")?)?;
        let plain = protocol::decrypt_file(&package, &key, id, &self.npub(), &record.view.name)?;
        let destination = self.received_dir.join(format!("{id}-{}", record.view.name));
        tokio::fs::write(&destination, plain).await?;
        self.store.update(|state| {
            if let Some(r) = state.transfers.iter_mut().find(|r| r.view.id == id) {
                r.view.status = "completed".into();
                r.view.received_path = destination.to_string_lossy().into_owned();
                r.view.updated_at = now_secs();
                r.key_b64 = None;
            }
        })?;
        let complete = FileMessage::Complete {
            transfer_id: id.to_string(),
            sender_npub: self.npub(),
            recipient_npub: sender_npub.to_string(),
        };
        let _ = self.send_file_message(sender_npub, &complete).await;
        Ok(())
    }

    async fn send_file_message(&self, npub: &str, message: &FileMessage) -> Result<()> {
        let target = PublicKey::from_bech32(npub)?;
        let event = protocol::private_file_event(&self.keys, &target, message).await?;
        let frame = protocol::mesh_event_frame(&event)?;
        let ip = protocol::peer_ipv6(npub)?;
        let url = format!("ws://[{ip}]:4870");
        let (mut socket, _) = tokio::time::timeout(
            Duration::from_secs(20),
            tokio_tungstenite::connect_async(url),
        )
        .await
        .context("peer relay connection timed out")??;
        socket.send(Message::Text(frame.into())).await?;
        if let Ok(Some(reply)) = tokio::time::timeout(Duration::from_secs(20), socket.next()).await
        {
            let reply = reply?;
            if let Message::Text(text) = reply {
                let value: serde_json::Value = serde_json::from_str(&text)?;
                let ok = value
                    .as_array()
                    .and_then(|v| v.get(2))
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                if !ok {
                    bail!("peer relay refused file-control event");
                }
            }
        }
        let _ = socket.close(None).await;
        Ok(())
    }

    pub async fn handle_mesh_frame(self: &Arc<Self>, frame: &str) -> Result<Event> {
        let event = protocol::unwrap_mesh_event(frame)?;
        event.verify()?;
        self.handle_file_event(event.clone()).await?;
        Ok(event)
    }

    pub async fn blob(&self, hash: &str) -> Result<Vec<u8>> {
        if !protocol::valid_blob_hash(hash) {
            bail!("invalid blob hash");
        }
        Ok(tokio::fs::read(self.blobs_dir.join(hash)).await?)
    }

    fn peer_name(&self, npub: &str) -> String {
        self.store
            .snapshot()
            .circle
            .into_iter()
            .find(|p| p.npub == npub)
            .map(|p| p.name)
            .unwrap_or_else(|| short_name(npub))
    }

    fn transfer(&self, id: &str, direction: &str) -> Result<TransferRecord> {
        self.store
            .snapshot()
            .transfers
            .into_iter()
            .find(|r| r.view.id == id && r.view.direction == direction)
            .context("file transfer not found")
    }

    fn transfer_in_state(&self, id: &str, direction: &str, npub: &str, status: &str) -> bool {
        self.store.snapshot().transfers.iter().any(|r| {
            r.view.id == id
                && r.view.direction == direction
                && r.view.peer_npub == npub
                && r.view.status == status
        })
    }

    fn set_transfer_status(&self, id: &str, status: &str, error: &str) -> Result<()> {
        self.store.update(|state| {
            if let Some(record) = state.transfers.iter_mut().find(|r| r.view.id == id) {
                record.view.status = status.to_string();
                record.view.error = error.to_string();
                record.view.updated_at = now_secs();
            }
        })
    }

    fn cleanup_transfer_secrets(&self, id: &str) -> Result<()> {
        let record = self.store.update(|state| {
            state
                .transfers
                .iter_mut()
                .find(|r| r.view.id == id)
                .map(|r| {
                    r.key_b64 = None;
                    r.source_path.take()
                })
        })?;
        if let Some(Some(path)) = record {
            let _ = std::fs::remove_file(path);
        }
        Ok(())
    }
}

fn prune_transfers(transfers: &mut Vec<TransferRecord>) {
    if transfers.len() < MAX_TRACKED_TRANSFERS {
        return;
    }
    transfers.retain(|r| !matches!(r.view.status.as_str(), "completed" | "denied" | "failed"));
    if transfers.len() >= MAX_TRACKED_TRANSFERS {
        transfers.sort_by_key(|r| r.view.updated_at);
        transfers.truncate(MAX_TRACKED_TRANSFERS - 1);
    }
}
