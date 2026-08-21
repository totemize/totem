use std::net::Ipv6Addr;

use anyhow::{bail, Context, Result};
use base64::{engine::general_purpose, Engine as _};
use chacha20poly1305::aead::{Aead, AeadCore, KeyInit, OsRng, Payload};
use chacha20poly1305::{Key, XChaCha20Poly1305, XNonce};
use nostr::nips::nip44::{self, Version};
use nostr::prelude::*;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::model::{now_secs, MAX_FILE_BYTES, PAIR_TTL_SECS};

pub const KIND_PAIR_REQUEST: u16 = 9101;
pub const KIND_PAIR_ACCEPT: u16 = 9102;
pub const KIND_PAIR_REMOVE: u16 = 9103;
pub const MAX_PACKAGE_BYTES: u64 = MAX_FILE_BYTES as u64 + MAGIC.len() as u64 + 24 + 16;
const MAGIC: &[u8] = b"MYCO-FILE-V1\0";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum FileMessage {
    #[serde(rename = "myco.file_offer.v1")]
    Offer {
        transfer_id: String,
        sender_npub: String,
        recipient_npub: String,
        filename: String,
        mime: String,
        size: u64,
        issued_at: u64,
        expires_at: u64,
    },
    #[serde(rename = "myco.file_response.v1")]
    Response {
        transfer_id: String,
        sender_npub: String,
        recipient_npub: String,
        accepted: bool,
        reason: Option<String>,
    },
    #[serde(rename = "myco.file_ready.v1")]
    Ready {
        transfer_id: String,
        sender_npub: String,
        recipient_npub: String,
        filename: String,
        mime: String,
        size: u64,
        blob_hash: String,
        ciphertext_size: u64,
        key_wrap: String,
    },
    #[serde(rename = "myco.file_complete.v1")]
    Complete {
        transfer_id: String,
        sender_npub: String,
        recipient_npub: String,
    },
}

impl FileMessage {
    pub fn transfer_id(&self) -> &str {
        match self {
            Self::Offer { transfer_id, .. }
            | Self::Response { transfer_id, .. }
            | Self::Ready { transfer_id, .. }
            | Self::Complete { transfer_id, .. } => transfer_id,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PairPayload {
    #[serde(default = "pair_version")]
    pub v: u8,
    pub npub: String,
    pub name: String,
    pub secret: String,
}

fn pair_version() -> u8 {
    1
}

pub fn build_pair_uri(payload: &PairPayload) -> Result<String> {
    let encoded = general_purpose::URL_SAFE_NO_PAD.encode(serde_json::to_vec(payload)?);
    Ok(format!("myco://pair/{encoded}"))
}

pub fn parse_pair_uri(uri: &str) -> Result<PairPayload> {
    let encoded = uri
        .trim()
        .strip_prefix("myco://pair/")
        .context("not a Myco pairing URI")?;
    let payload: PairPayload =
        serde_json::from_slice(&general_purpose::URL_SAFE_NO_PAD.decode(encoded)?)?;
    if payload.v != 1 || payload.npub.is_empty() || payload.secret.is_empty() {
        bail!("invalid Myco pairing payload");
    }
    PublicKey::from_bech32(&payload.npub).context("invalid pairing npub")?;
    Ok(payload)
}

pub fn new_secret() -> String {
    let nonce = XChaCha20Poly1305::generate_nonce(&mut OsRng);
    general_purpose::URL_SAFE_NO_PAD.encode(nonce)
}

pub fn new_transfer_id() -> String {
    let nonce = XChaCha20Poly1305::generate_nonce(&mut OsRng);
    hex::encode(&nonce[..16])
}

pub fn peer_ipv6(npub: &str) -> Result<Ipv6Addr> {
    let public_key = PublicKey::from_bech32(npub).context("invalid peer npub")?;
    // FIPS derives node_addr from the raw x-only public key, not its npub text.
    let digest = Sha256::digest(public_key.as_bytes());
    let mut bytes = [0u8; 16];
    bytes[0] = 0xfd;
    bytes[1..].copy_from_slice(&digest[..15]);
    Ok(Ipv6Addr::from(bytes))
}

pub fn npub_for_ipv6<'a>(npubs: impl Iterator<Item = &'a str>, ip: Ipv6Addr) -> Option<String> {
    npubs
        .filter_map(|npub| peer_ipv6(npub).ok().map(|candidate| (npub, candidate)))
        .find(|(_, candidate)| *candidate == ip)
        .map(|(npub, _)| npub.to_string())
}

pub fn pair_event(
    keys: &Keys,
    kind: u16,
    target_npub: &str,
    name: &str,
    secret: &str,
) -> Result<Event> {
    let target = PublicKey::from_bech32(target_npub)?;
    let expiration = (now_secs() + PAIR_TTL_SECS).to_string();
    let mut tags = vec![
        Tag::parse(["p", &target.to_hex()])?,
        Tag::parse(["n", name])?,
        Tag::parse(["expiration", &expiration])?,
    ];
    if !secret.is_empty() {
        tags.push(Tag::parse(["secret", secret])?);
    }
    Ok(EventBuilder::new(Kind::from(kind), "")
        .tags(tags)
        .finalize(keys)?)
}

pub fn tag_value(event: &Event, key: &str) -> Option<String> {
    event.tags.iter().find_map(|tag| {
        let parts = tag.as_slice();
        (parts.first().map(String::as_str) == Some(key))
            .then(|| parts.get(1).cloned())
            .flatten()
    })
}

pub fn addressed_to(event: &Event, keys: &Keys) -> bool {
    tag_value(event, "p").is_some_and(|p| p == keys.public_key().to_hex())
}

pub fn event_expired(event: &Event) -> bool {
    tag_value(event, "expiration")
        .and_then(|v| v.parse::<u64>().ok())
        .is_some_and(|expiration| expiration <= now_secs())
}

pub async fn private_file_event(
    keys: &Keys,
    recipient: &PublicKey,
    message: &FileMessage,
) -> Result<Event> {
    let content = serde_json::to_string(message)?;
    Ok(PrivateDirectMessageBuilder::new(*recipient, content).finalize(keys)?)
}

pub async fn extract_file_message(keys: &Keys, event: &Event) -> Result<(PublicKey, FileMessage)> {
    if event.kind != Kind::GiftWrap {
        bail!("not a gift wrap");
    }
    let unwrapped = nostr::nips::nip59::extract_rumor(keys, event)?;
    if unwrapped.rumor.kind != Kind::PrivateDirectMessage {
        bail!("not a private message rumor");
    }
    let message = serde_json::from_str(&unwrapped.rumor.content)?;
    Ok((unwrapped.sender, message))
}

pub fn mesh_event_frame(event: &Event) -> Result<String> {
    let event = serde_json::to_value(event)?;
    Ok(serde_json::json!(["MESH", {}, ["EVENT", event]]).to_string())
}

pub fn unwrap_mesh_event(text: &str) -> Result<Event> {
    let value: serde_json::Value = serde_json::from_str(text)?;
    let outer = value.as_array().context("not an array")?;
    let inner = if outer.first().and_then(|v| v.as_str()) == Some("MESH") {
        outer.get(2).context("missing MESH payload")?
    } else {
        &value
    };
    let message = inner.as_array().context("not a NIP-01 message")?;
    if message.first().and_then(|v| v.as_str()) != Some("EVENT") {
        bail!("not an EVENT message");
    }
    Ok(serde_json::from_value(
        message.get(1).context("missing event")?.clone(),
    )?)
}

pub fn valid_transfer_id(id: &str) -> bool {
    id.len() == 32 && id.bytes().all(|b| b.is_ascii_hexdigit())
}

pub fn valid_blob_hash(hash: &str) -> bool {
    hash.len() == 64
        && hash
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

pub fn safe_filename(name: &str, fallback: &str) -> String {
    let candidate = std::path::Path::new(name)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or(fallback)
        .trim();
    let cleaned: String = candidate
        .chars()
        .map(|c| match c {
            '/' | '\\' | '\0' => '_',
            c if c.is_control() => '_',
            c => c,
        })
        .collect();
    if cleaned.is_empty() {
        fallback.to_string()
    } else {
        cleaned.chars().take(180).collect()
    }
}

pub fn rejected_payload(filename: &str, mime: &str) -> Option<String> {
    const BLOCKED_MIME: &[&str] = &[
        "application/vnd.android.package-archive",
        "application/vnd.android.dex",
        "application/java-archive",
        "application/x-executable",
        "application/x-sharedlib",
    ];
    const BLOCKED_EXT: &[&str] = &[
        "apk", "apks", "apex", "aab", "xapk", "dex", "dm", "jar", "so",
    ];
    let claimed = mime.trim().to_ascii_lowercase();
    if BLOCKED_MIME.iter().any(|m| claimed == *m) {
        return Some("app packages cannot be shared over Myco".to_string());
    }
    let extension = std::path::Path::new(filename)
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_ascii_lowercase());
    extension
        .filter(|e| BLOCKED_EXT.contains(&e.as_str()))
        .map(|e| format!(".{e} files cannot be shared over Myco"))
}

pub fn encrypt_file(
    plaintext: &[u8],
    transfer_id: &str,
    recipient_npub: &str,
    filename: &str,
) -> Result<(Vec<u8>, Vec<u8>)> {
    if plaintext.len() > MAX_FILE_BYTES {
        bail!("file is larger than the 64 MiB Myco limit");
    }
    let key = XChaCha20Poly1305::generate_key(&mut OsRng);
    let nonce = XChaCha20Poly1305::generate_nonce(&mut OsRng);
    let cipher = XChaCha20Poly1305::new(&key);
    let aad = file_aad(transfer_id, recipient_npub, filename);
    let ciphertext = cipher
        .encrypt(
            &nonce,
            Payload {
                msg: plaintext,
                aad: &aad,
            },
        )
        .map_err(|_| anyhow::anyhow!("file encryption failed"))?;
    let mut package = Vec::with_capacity(MAGIC.len() + nonce.len() + ciphertext.len());
    package.extend_from_slice(MAGIC);
    package.extend_from_slice(&nonce);
    package.extend_from_slice(&ciphertext);
    Ok((package, key.to_vec()))
}

pub fn decrypt_file(
    package: &[u8],
    key: &[u8],
    transfer_id: &str,
    recipient_npub: &str,
    filename: &str,
) -> Result<Vec<u8>> {
    if key.len() != 32 || package.len() < MAGIC.len() + 24 + 16 {
        bail!("invalid encrypted file package");
    }
    if &package[..MAGIC.len()] != MAGIC {
        bail!("unrecognised encrypted file package");
    }
    let cipher = XChaCha20Poly1305::new(Key::from_slice(key));
    let aad = file_aad(transfer_id, recipient_npub, filename);
    cipher
        .decrypt(
            XNonce::from_slice(&package[MAGIC.len()..MAGIC.len() + 24]),
            Payload {
                msg: &package[MAGIC.len() + 24..],
                aad: &aad,
            },
        )
        .map_err(|_| anyhow::anyhow!("file authentication failed"))
}

fn file_aad(transfer_id: &str, recipient_npub: &str, filename: &str) -> Vec<u8> {
    format!("myco-file-v1|{transfer_id}|{recipient_npub}|{filename}").into_bytes()
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub fn encode_key(key: &[u8]) -> String {
    general_purpose::STANDARD.encode(key)
}

pub fn decode_key(value: &str) -> Result<Vec<u8>> {
    let key = general_purpose::STANDARD.decode(value)?;
    if key.len() != 32 {
        bail!("invalid file key length");
    }
    Ok(key)
}

pub fn wrap_key(sender: &Keys, recipient: &PublicKey, key: &[u8]) -> Result<String> {
    Ok(nip44::encrypt(
        sender.secret_key(),
        recipient,
        encode_key(key),
        Version::default(),
    )?)
}

pub fn unwrap_key(recipient: &Keys, sender: &PublicKey, wrapped: &str) -> Result<Vec<u8>> {
    decode_key(&nip44::decrypt(recipient.secret_key(), sender, wrapped)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pair_uri_matches_myco_shape() {
        let keys = Keys::generate();
        let payload = PairPayload {
            v: 1,
            npub: keys.public_key().to_bech32().unwrap(),
            name: "Totem test".into(),
            secret: new_secret(),
        };
        assert_eq!(
            parse_pair_uri(&build_pair_uri(&payload).unwrap())
                .unwrap()
                .npub,
            payload.npub
        );
    }

    #[test]
    fn control_messages_match_myco_wire_field_names() {
        let message = FileMessage::Ready {
            transfer_id: "00112233445566778899aabbccddeeff".into(),
            sender_npub: "npub-sender".into(),
            recipient_npub: "npub-recipient".into(),
            filename: "notes.txt".into(),
            mime: "text/plain".into(),
            size: 5,
            blob_hash: "ab".repeat(32),
            ciphertext_size: 58,
            key_wrap: "wrapped".into(),
        };
        assert_eq!(
            serde_json::to_value(message).unwrap(),
            serde_json::json!({
                "type": "myco.file_ready.v1",
                "transfer_id": "00112233445566778899aabbccddeeff",
                "sender_npub": "npub-sender",
                "recipient_npub": "npub-recipient",
                "filename": "notes.txt",
                "mime": "text/plain",
                "size": 5,
                "blob_hash": "abababababababababababababababababababababababababababababababab",
                "ciphertext_size": 58,
                "key_wrap": "wrapped"
            })
        );
    }

    #[test]
    fn mesh_file_frame_uses_myco_ttl_zero_envelope() {
        let sender = Keys::generate();
        let recipient = Keys::generate().public_key().to_bech32().unwrap();
        let event = pair_event(
            &sender,
            KIND_PAIR_REQUEST,
            &recipient,
            "Totem test",
            "secret",
        )
        .unwrap();
        let frame: serde_json::Value =
            serde_json::from_str(&mesh_event_frame(&event).unwrap()).unwrap();
        assert_eq!(frame[0], "MESH");
        assert_eq!(frame[1], serde_json::json!({}));
        assert_eq!(frame[2][0], "EVENT");
        assert_eq!(frame[2][1]["id"], event.id.to_hex());
    }

    #[test]
    fn encrypted_file_round_trips() {
        let (package, key) = encrypt_file(
            b"hello",
            "00112233445566778899aabbccddeeff",
            "npub",
            "x.txt",
        )
        .unwrap();
        let plain = decrypt_file(
            &package,
            &key,
            "00112233445566778899aabbccddeeff",
            "npub",
            "x.txt",
        )
        .unwrap();
        assert_eq!(plain, b"hello");
    }

    #[test]
    fn peer_ipv6_matches_live_fips_nodes() {
        let cases = [
            (
                "npub1eu0clm0nsxwavcsj07at3sy7v52tuwgw4qpeqsyxgkeqg7krc7ps77c20q",
                "fd19:c4f2:206a:28b7:f4e7:fd3e:986b:5560",
            ),
            (
                "npub1j0adney3t3tuvcaz6wv6eahpkhfrl8rwhry58n2u4njuxz0j04lsrudpf6",
                "fd27:7759:67a2:892d:aceb:b1f1:dc56:dc60",
            ),
            (
                "npub1rx7epldvux4d306aasw0n6y7wn9je0wa3yw4f8djpsw28g8zqzxsgg2g35",
                "fd71:93b2:349f:afed:9b57:336c:1a1e:871f",
            ),
        ];
        for (npub, expected) in cases {
            assert_eq!(peer_ipv6(npub).unwrap().to_string(), expected);
        }
    }
}
