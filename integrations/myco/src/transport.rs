use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::RwLock;
use std::time::Duration;

use anyhow::{bail, Context, Result};
use base64::{engine::general_purpose, Engine as _};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};

const MYCO_AWARE_SERVICE: &str = "myco.fips.v1";
const FIPS_CONTROL_SOCKET: &str = "/run/fips/control.sock";
const LEGACY_AWARE_UDP_PORT: u16 = 4871;
const BECH32_CHARSET: &str = "qpzry9x8gf2tvdw0s3jn54khce6mua7l";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TransportKind {
    WifiAware,
    Lan,
    SoftAp,
    BluetoothCoc,
}

impl TransportKind {
    pub fn udp_lane(value: &str) -> Result<Self> {
        match value {
            "lan" => Ok(Self::Lan),
            "softap" | "soft-ap" => Ok(Self::SoftAp),
            _ => bail!("UDP lane must be lan or softap"),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PeerLane {
    pub npub: String,
    pub transport: TransportKind,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resource_id: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TransportStatus {
    pub device_manager_url: String,
    pub device_manager: Option<Value>,
    pub device_manager_error: Option<String>,
    pub fips_control_socket: &'static str,
    pub lanes: Vec<PeerLane>,
    pub application_path: &'static str,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct NanDiscovery {
    pub id: String,
    pub interface: String,
    pub service_name: String,
    pub active: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct NanDataPath {
    pub id: String,
    pub match_id: String,
    pub interface: String,
    pub peer_address: String,
    pub local_ipv6: String,
    pub peer_ipv6: String,
    pub port: u16,
    pub state: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct NanMatch {
    pub id: String,
    pub session_id: String,
    pub peer_address: String,
    pub service_info_base64: String,
    pub last_seen_at: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct NanFollowup {
    pub id: String,
    pub session_id: String,
    pub match_id: String,
    pub peer_address: String,
    pub payload_base64: String,
    pub direction: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct AwarePeerIdentity {
    pub match_id: String,
    pub session_id: String,
    pub peer_address: String,
    pub npub: String,
    pub port: u16,
    pub received_at: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct L2capListener {
    pub id: String,
    pub local_address: String,
    pub address_type: String,
    pub psm: u16,
    pub mtu: u16,
    pub service_uuid: String,
    pub advertisement_id: Option<String>,
    pub listening: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct L2capConnection {
    pub id: String,
    pub peer_address: String,
    pub address_type: String,
    pub psm: u16,
    pub mtu: u16,
    pub handed_off: bool,
}

pub struct TransportManager {
    client: reqwest::Client,
    device_manager_url: String,
    fips_control_socket: PathBuf,
    lanes: RwLock<HashMap<String, Vec<PeerLane>>>,
    aware_announced: RwLock<HashMap<String, String>>,
    aware_identities: RwLock<HashMap<String, AwarePeerIdentity>>,
}

impl TransportManager {
    pub fn new(device_manager_url: String) -> Result<Self> {
        Self::with_fips_socket(device_manager_url, PathBuf::from(FIPS_CONTROL_SOCKET))
    }

    fn with_fips_socket(device_manager_url: String, fips_control_socket: PathBuf) -> Result<Self> {
        let device_manager_url = device_manager_url.trim_end_matches('/').to_string();
        if !device_manager_url.starts_with("http://127.0.0.1:")
            && !device_manager_url.starts_with("http://[::1]:")
        {
            bail!("device manager URL must use an explicit loopback address");
        }
        Ok(Self {
            client: reqwest::Client::builder()
                .connect_timeout(Duration::from_secs(3))
                .timeout(Duration::from_secs(125))
                .build()?,
            device_manager_url,
            fips_control_socket,
            lanes: RwLock::new(HashMap::new()),
            aware_announced: RwLock::new(HashMap::new()),
            aware_identities: RwLock::new(HashMap::new()),
        })
    }

    pub async fn status(&self) -> TransportStatus {
        let (device_manager, device_manager_error) =
            match self.get_json("/network/capabilities").await {
                Ok(value) => (Some(value), None),
                Err(error) => (None, Some(stable_error(&error))),
            };
        TransportStatus {
            device_manager_url: self.device_manager_url.clone(),
            device_manager,
            device_manager_error,
            fips_control_socket: FIPS_CONTROL_SOCKET,
            lanes: self.registered_lanes(),
            application_path: "fips-tun",
        }
    }

    pub async fn connect_udp_lane(
        &self,
        npub: &str,
        address: &str,
        kind: TransportKind,
    ) -> Result<PeerLane> {
        if !matches!(kind, TransportKind::Lan | TransportKind::SoftAp) {
            bail!("only LAN and SoftAP can be registered as UDP lanes");
        }
        validate_udp_endpoint(address)?;
        self.fips_connect(npub, address, "udp").await?;
        let lane = PeerLane {
            npub: npub.to_string(),
            transport: kind,
            address: Some(address.to_string()),
            resource_id: None,
        };
        self.replace_lane(lane.clone());
        Ok(lane)
    }

    pub fn remove_udp_lane(&self, npub: &str, kind: TransportKind) {
        let mut lanes = self.lanes.write().expect("transport lane lock poisoned");
        if let Some(values) = lanes.get_mut(npub) {
            values.retain(|lane| lane.transport != kind);
            if values.is_empty() {
                lanes.remove(npub);
            }
        }
    }

    pub async fn start_aware_discovery(
        &self,
        udp_port: u16,
        duration: u16,
    ) -> Result<NanDiscovery> {
        if udp_port == 0 {
            bail!("Wi-Fi Aware UDP port must be non-zero");
        }
        self.post_json(
            "/network/wifi/aware/discovery",
            json!({
                "service_name": MYCO_AWARE_SERVICE,
                "service_info_base64": "",
                "duration_seconds": duration,
                "timeout_seconds": 15,
            }),
        )
        .await
    }

    pub async fn create_aware_path(
        &self,
        npub: &str,
        match_id: &str,
        port: u16,
    ) -> Result<NanDataPath> {
        let path: NanDataPath = self
            .post_json(
                "/network/wifi/aware/data-paths",
                json!({"match_id": match_id, "port": port, "timeout_seconds": 30}),
            )
            .await?;
        let endpoint = scoped_udp_endpoint(&path)?;
        if let Err(error) = self.fips_connect(npub, &endpoint, "udp").await {
            let _ = self
                .delete(&format!("/network/wifi/aware/data-paths/{}", path.id))
                .await;
            return Err(error).context("inject Wi-Fi Aware UDP peer into FIPS");
        }
        self.replace_lane(PeerLane {
            npub: npub.to_string(),
            transport: TransportKind::WifiAware,
            address: Some(endpoint),
            resource_id: Some(path.id.clone()),
        });
        Ok(path)
    }

    pub async fn aware_matches(&self) -> Result<Vec<NanMatch>> {
        let value = self.get_json("/network/wifi/aware/matches").await?;
        serde_json::from_value(value).context("decode Wi-Fi Aware matches")
    }

    pub async fn exchange_aware_identity(
        &self,
        session_id: &str,
        local_npub: &str,
        port: u16,
    ) -> Result<Vec<AwarePeerIdentity>> {
        validate_npub(local_npub)?;
        if port == 0 {
            bail!("Wi-Fi Aware UDP port must be non-zero");
        }
        let payload = format!("{local_npub}|{port}");
        let payload_base64 = general_purpose::STANDARD.encode(payload.as_bytes());
        let matches = self.aware_matches().await?;
        for matched in matches
            .into_iter()
            .filter(|matched| matched.session_id == session_id)
        {
            let should_send = {
                let mut announced = self
                    .aware_announced
                    .write()
                    .expect("Aware announcement lock poisoned");
                if announced.contains_key(&matched.id) {
                    false
                } else {
                    announced.insert(matched.id.clone(), session_id.to_string());
                    true
                }
            };
            if !should_send {
                continue;
            }
            let result: Result<NanFollowup> = self
                .post_json(
                    "/network/wifi/aware/followups",
                    json!({
                        "match_id": matched.id.clone(),
                        "payload_base64": payload_base64,
                        "timeout_seconds": 15,
                    }),
                )
                .await;
            if let Err(error) = result {
                self.aware_announced
                    .write()
                    .expect("Aware announcement lock poisoned")
                    .remove(&matched.id);
                return Err(error).context("send Wi-Fi Aware identity follow-up");
            }
        }

        let value = self.get_json("/network/wifi/aware/followups").await?;
        let followups: Vec<NanFollowup> =
            serde_json::from_value(value).context("decode Wi-Fi Aware follow-ups")?;
        let mut identities = self
            .aware_identities
            .write()
            .expect("Aware identity lock poisoned");
        for followup in followups.into_iter().filter(|followup| {
            followup.session_id == session_id && followup.direction == "received"
        }) {
            let Ok(bytes) = general_purpose::STANDARD.decode(&followup.payload_base64) else {
                continue;
            };
            let Ok(text) = std::str::from_utf8(&bytes) else {
                continue;
            };
            let Ok((npub, port)) = parse_aware_identity(text) else {
                continue;
            };
            identities.insert(
                followup.match_id.clone(),
                AwarePeerIdentity {
                    match_id: followup.match_id,
                    session_id: followup.session_id,
                    peer_address: followup.peer_address,
                    npub,
                    port,
                    received_at: followup.created_at,
                },
            );
        }
        let mut result: Vec<_> = identities
            .values()
            .filter(|identity| identity.session_id == session_id)
            .cloned()
            .collect();
        result.sort_by(|a, b| a.match_id.cmp(&b.match_id));
        Ok(result)
    }

    pub fn aware_identities(&self) -> Vec<AwarePeerIdentity> {
        let mut values: Vec<_> = self
            .aware_identities
            .read()
            .expect("Aware identity lock poisoned")
            .values()
            .cloned()
            .collect();
        values.sort_by(|a, b| a.match_id.cmp(&b.match_id));
        values
    }

    pub fn aware_identity(&self, match_id: &str) -> Option<AwarePeerIdentity> {
        self.aware_identities
            .read()
            .expect("Aware identity lock poisoned")
            .get(match_id)
            .cloned()
    }

    pub async fn stop_aware_discovery(&self, session_id: &str) -> Result<()> {
        self.delete(&format!("/network/wifi/aware/discovery/{session_id}"))
            .await?;
        self.aware_announced
            .write()
            .expect("Aware announcement lock poisoned")
            .retain(|_, value| value != session_id);
        self.aware_identities
            .write()
            .expect("Aware identity lock poisoned")
            .retain(|_, value| value.session_id != session_id);
        Ok(())
    }

    pub async fn remove_aware_path(&self, data_path_id: &str) -> Result<()> {
        self.delete(&format!("/network/wifi/aware/data-paths/{data_path_id}"))
            .await?;
        let mut lanes = self.lanes.write().expect("transport lane lock poisoned");
        lanes.retain(|_, values| {
            values.retain(|lane| lane.resource_id.as_deref() != Some(data_path_id));
            !values.is_empty()
        });
        Ok(())
    }

    pub async fn connect_coc(
        &self,
        npub: &str,
        peer_address: &str,
        psm: u16,
        mtu: u16,
        address_type: &str,
    ) -> Result<L2capConnection> {
        let connection: L2capConnection = self
            .post_json(
                "/network/bluetooth/l2cap/connections",
                json!({
                    "peer_address": peer_address,
                    "psm": psm,
                    "mtu": mtu,
                    "address_type": address_type,
                    "timeout_seconds": 30,
                }),
            )
            .await?;
        let handoff_path = format!(
            "/network/bluetooth/l2cap/connections/{}/fips-handoff",
            connection.id
        );
        if let Err(error) = self
            .post_json::<Value>(&handoff_path, json!({"timeout_seconds": 15}))
            .await
        {
            let _ = self
                .delete(&format!(
                    "/network/bluetooth/l2cap/connections/{}",
                    connection.id
                ))
                .await;
            return Err(error).context("hand off LE CoC connection to FIPS");
        }
        let mut connection = connection;
        connection.handed_off = true;
        self.replace_lane(PeerLane {
            npub: npub.to_string(),
            transport: TransportKind::BluetoothCoc,
            address: None,
            resource_id: Some(connection.id.clone()),
        });
        Ok(connection)
    }

    pub async fn create_coc_listener(
        &self,
        psm: u16,
        mtu: u16,
        address_type: &str,
    ) -> Result<L2capListener> {
        self.post_json(
            "/network/bluetooth/l2cap/listeners",
            json!({
                "psm": psm,
                "mtu": mtu,
                "address_type": address_type,
                "timeout_seconds": 30,
            }),
        )
        .await
    }

    pub async fn coc_listeners(&self) -> Result<Vec<L2capListener>> {
        let value = self.get_json("/network/bluetooth/l2cap/listeners").await?;
        serde_json::from_value(value).context("decode LE CoC listeners")
    }

    pub async fn close_coc_listener(&self, listener_id: &str) -> Result<()> {
        self.delete(&format!("/network/bluetooth/l2cap/listeners/{listener_id}"))
            .await?;
        Ok(())
    }

    pub async fn handoff_coc(&self, npub: &str, connection_id: &str) -> Result<Value> {
        let result = self
            .post_json(
                &format!("/network/bluetooth/l2cap/connections/{connection_id}/fips-handoff"),
                json!({"timeout_seconds": 15}),
            )
            .await?;
        self.replace_lane(PeerLane {
            npub: npub.to_string(),
            transport: TransportKind::BluetoothCoc,
            address: None,
            resource_id: Some(connection_id.to_string()),
        });
        Ok(result)
    }

    fn registered_lanes(&self) -> Vec<PeerLane> {
        let lanes = self.lanes.read().expect("transport lane lock poisoned");
        let mut result: Vec<_> = lanes.values().flatten().cloned().collect();
        result.sort_by(|a, b| (&a.npub, &a.address).cmp(&(&b.npub, &b.address)));
        result
    }

    fn replace_lane(&self, lane: PeerLane) {
        let mut lanes = self.lanes.write().expect("transport lane lock poisoned");
        let values = lanes.entry(lane.npub.clone()).or_default();
        values.retain(|value| value.transport != lane.transport);
        values.push(lane);
    }

    async fn fips_connect(&self, npub: &str, address: &str, transport: &str) -> Result<Value> {
        let request = json!({
            "command": "connect",
            "params": {"npub": npub, "address": address, "transport": transport},
        });
        let response = fips_request(&self.fips_control_socket, &request).await?;
        if response.get("status").and_then(Value::as_str) != Some("ok") {
            let message = response
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("FIPS rejected transport handoff");
            bail!("FIPS control error: {message}");
        }
        Ok(response.get("data").cloned().unwrap_or(Value::Null))
    }

    async fn get_json(&self, path: &str) -> Result<Value> {
        let response = self
            .client
            .get(format!("{}{path}", self.device_manager_url))
            .send()
            .await?;
        decode_response(response).await
    }

    async fn post_json<T: serde::de::DeserializeOwned>(
        &self,
        path: &str,
        body: Value,
    ) -> Result<T> {
        let response = self
            .client
            .post(format!("{}{path}", self.device_manager_url))
            .json(&body)
            .send()
            .await?;
        decode_response(response).await
    }

    async fn delete(&self, path: &str) -> Result<Value> {
        let response = self
            .client
            .delete(format!("{}{path}", self.device_manager_url))
            .send()
            .await?;
        decode_response(response).await
    }
}

async fn fips_request(path: &Path, request: &Value) -> Result<Value> {
    let mut stream = tokio::net::UnixStream::connect(path)
        .await
        .with_context(|| format!("connect to FIPS control socket {}", path.display()))?;
    let mut bytes = serde_json::to_vec(request)?;
    if bytes.len() > 4096 {
        bail!("FIPS control request exceeds limit");
    }
    bytes.push(b'\n');
    stream.write_all(&bytes).await?;
    let mut response = String::new();
    let mut reader = BufReader::new(stream).take(64 * 1024 + 1);
    tokio::time::timeout(Duration::from_secs(15), reader.read_line(&mut response))
        .await
        .context("FIPS control request timed out")??;
    if response.len() > 64 * 1024 {
        bail!("FIPS control response exceeds limit");
    }
    serde_json::from_str(&response).context("decode FIPS control response")
}

async fn decode_response<T: serde::de::DeserializeOwned>(response: reqwest::Response) -> Result<T> {
    let status = response.status();
    let bytes = response.bytes().await?;
    if !status.is_success() {
        let detail = serde_json::from_slice::<Value>(&bytes)
            .ok()
            .and_then(|value| value.get("detail").cloned())
            .unwrap_or_else(|| Value::String("operation failed".into()));
        bail!("device manager returned {status}: {detail}");
    }
    serde_json::from_slice(&bytes).context("decode device manager response")
}

fn validate_udp_endpoint(address: &str) -> Result<()> {
    if address.is_empty()
        || address.len() > 320
        || address.contains(['/', '#', '?', '@'])
        || !address.contains(':')
    {
        bail!("invalid UDP endpoint");
    }
    Ok(())
}

fn validate_npub(npub: &str) -> Result<()> {
    let Some(data) = npub.strip_prefix("npub1") else {
        bail!("invalid npub in Wi-Fi Aware identity");
    };
    if data.len() != 58
        || !data
            .chars()
            .all(|character| BECH32_CHARSET.contains(character))
    {
        bail!("invalid npub in Wi-Fi Aware identity");
    }
    Ok(())
}

fn parse_aware_identity(value: &str) -> Result<(String, u16)> {
    let (npub, port) = match value.split_once('|') {
        Some((npub, port)) if !port.contains('|') => (
            npub,
            port.parse::<u16>()
                .context("invalid Wi-Fi Aware identity port")?,
        ),
        Some(_) => bail!("invalid Wi-Fi Aware identity fields"),
        None => (value, LEGACY_AWARE_UDP_PORT),
    };
    validate_npub(npub)?;
    if port == 0 {
        bail!("invalid Wi-Fi Aware identity port");
    }
    Ok((npub.to_string(), port))
}

fn scoped_udp_endpoint(path: &NanDataPath) -> Result<String> {
    let (address, scope) = path
        .peer_ipv6
        .split_once('%')
        .context("Wi-Fi Aware peer IPv6 is missing an interface scope")?;
    let _: std::net::Ipv6Addr = address.parse().context("invalid Wi-Fi Aware peer IPv6")?;
    let scope_id = if scope.chars().all(|c| c.is_ascii_digit()) {
        scope.to_string()
    } else {
        let interface = if scope.is_empty() {
            &path.interface
        } else {
            scope
        };
        if !interface
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
        {
            bail!("invalid Wi-Fi Aware interface scope");
        }
        std::fs::read_to_string(format!("/sys/class/net/{interface}/ifindex"))
            .with_context(|| format!("read interface index for {interface}"))?
            .trim()
            .parse::<u32>()
            .context("invalid interface index")?
            .to_string()
    };
    let endpoint = format!("[{address}%{scope_id}]:{}", path.port);
    validate_udp_endpoint(&endpoint)?;
    Ok(endpoint)
}

fn stable_error(error: &anyhow::Error) -> String {
    let message = error.to_string();
    if message.chars().count() > 240 {
        format!("{}…", message.chars().take(240).collect::<String>())
    } else {
        message
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::routing::{get, post};
    use axum::{Json, Router};
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::{Arc, Mutex};
    use tokio::net::UnixListener;
    use tokio::sync::oneshot;

    #[test]
    fn aware_identity_matches_android_wire_and_legacy_fallback() {
        let npub = "npub1eu0clm0nsxwavcsj07at3sy7v52tuwgw4qpeqsyxgkeqg7krc7ps77c20q";
        assert_eq!(
            parse_aware_identity(&format!("{npub}|4873")).unwrap(),
            (npub.to_string(), 4873)
        );
        assert_eq!(
            parse_aware_identity(npub).unwrap(),
            (npub.to_string(), LEGACY_AWARE_UDP_PORT)
        );
        assert!(parse_aware_identity("npub1bad|4873").is_err());
        assert!(parse_aware_identity(&format!("{npub}|0")).is_err());
    }

    #[test]
    fn device_manager_must_be_loopback() {
        assert!(TransportManager::new("http://192.168.8.9:8000".into()).is_err());
        assert!(TransportManager::new("http://127.0.0.1:8000".into()).is_ok());
    }

    #[tokio::test]
    async fn aware_discovery_and_followup_match_android_wire() {
        let local_npub = "npub1eu0clm0nsxwavcsj07at3sy7v52tuwgw4qpeqsyxgkeqg7krc7ps77c20q";
        let remote_npub = "npub1j0adney3t3tuvcaz6wv6eahpkhfrl8rwhry58n2u4njuxz0j04lsrudpf6";
        let discovery_request = Arc::new(Mutex::new(None));
        let followup_request = Arc::new(Mutex::new(None));
        let followup_count = Arc::new(AtomicUsize::new(0));
        let discovery_capture = Arc::clone(&discovery_request);
        let followup_capture = Arc::clone(&followup_request);
        let sent_count = Arc::clone(&followup_count);
        let received_payload =
            general_purpose::STANDARD.encode(format!("{remote_npub}|4873").as_bytes());

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        let server = tokio::spawn(async move {
            axum::serve(
                listener,
                Router::new()
                    .route(
                        "/network/wifi/aware/discovery",
                        post(move |Json(body): Json<Value>| {
                            let capture = Arc::clone(&discovery_capture);
                            async move {
                                *capture.lock().unwrap() = Some(body);
                                Json(json!({
                                    "id": "session-1",
                                    "interface": "totemnan0",
                                    "service_name": MYCO_AWARE_SERVICE,
                                    "active": true
                                }))
                            }
                        }),
                    )
                    .route(
                        "/network/wifi/aware/matches",
                        get(|| async {
                            Json(json!([{
                                "id": "match-1",
                                "session_id": "session-1",
                                "peer_address": "02:00:00:00:20:02",
                                "service_info_base64": "",
                                "last_seen_at": "2026-08-21T00:00:00Z"
                            }]))
                        }),
                    )
                    .route(
                        "/network/wifi/aware/followups",
                        get(move || {
                            let payload = received_payload.clone();
                            async move {
                                Json(json!([{
                                    "id": "received-1",
                                    "session_id": "session-1",
                                    "match_id": "match-1",
                                    "peer_address": "02:00:00:00:20:02",
                                    "payload_base64": payload,
                                    "direction": "received",
                                    "created_at": "2026-08-21T00:00:01Z"
                                }]))
                            }
                        })
                        .post(move |Json(body): Json<Value>| {
                            let capture = Arc::clone(&followup_capture);
                            let count = Arc::clone(&sent_count);
                            async move {
                                count.fetch_add(1, Ordering::SeqCst);
                                *capture.lock().unwrap() = Some(body.clone());
                                Json(json!({
                                    "id": "sent-1",
                                    "session_id": "session-1",
                                    "match_id": "match-1",
                                    "peer_address": "02:00:00:00:20:02",
                                    "payload_base64": body["payload_base64"],
                                    "direction": "sent",
                                    "created_at": "2026-08-21T00:00:01Z"
                                }))
                            }
                        }),
                    ),
            )
            .await
            .unwrap();
        });

        let manager = TransportManager::with_fips_socket(
            format!("http://{address}"),
            PathBuf::from("/unused"),
        )
        .unwrap();
        let session = manager.start_aware_discovery(4873, 60).await.unwrap();
        let identities = manager
            .exchange_aware_identity(&session.id, local_npub, 4873)
            .await
            .unwrap();
        manager
            .exchange_aware_identity(&session.id, local_npub, 4873)
            .await
            .unwrap();

        assert_eq!(
            discovery_request.lock().unwrap().as_ref().unwrap()["service_info_base64"],
            ""
        );
        let sent = followup_request.lock().unwrap().clone().unwrap();
        assert_eq!(sent["match_id"], "match-1");
        assert_eq!(
            general_purpose::STANDARD
                .decode(sent["payload_base64"].as_str().unwrap())
                .unwrap(),
            format!("{local_npub}|4873").as_bytes()
        );
        assert_eq!(identities.len(), 1);
        assert_eq!(identities[0].npub, remote_npub);
        assert_eq!(identities[0].port, 4873);
        assert_eq!(followup_count.load(Ordering::SeqCst), 1);
        server.abort();
    }

    #[tokio::test]
    async fn fips_control_request_is_bounded_line_json() {
        let directory = tempfile::tempdir().unwrap();
        let socket = directory.path().join("control.sock");
        let listener = UnixListener::bind(&socket).unwrap();
        let server = tokio::spawn(async move {
            let (stream, _) = listener.accept().await.unwrap();
            let (reader, mut writer) = stream.into_split();
            let mut request = String::new();
            BufReader::new(reader)
                .read_line(&mut request)
                .await
                .unwrap();
            let value: Value = serde_json::from_str(&request).unwrap();
            assert_eq!(value["command"], "connect");
            writer
                .write_all(b"{\"status\":\"ok\",\"data\":{\"transport\":\"udp\"}}\n")
                .await
                .unwrap();
        });
        let response = fips_request(
            &socket,
            &json!({"command": "connect", "params": {"transport": "udp"}}),
        )
        .await
        .unwrap();
        assert_eq!(response["status"], "ok");
        server.await.unwrap();
    }

    #[test]
    fn numeric_scope_builds_fips_udp_endpoint() {
        let path = NanDataPath {
            id: "nan-path-1".into(),
            match_id: "match-1".into(),
            interface: "aware_data0".into(),
            peer_address: "peer".into(),
            local_ipv6: "fe80::1%4".into(),
            peer_ipv6: "fe80::2%4".into(),
            port: 4873,
            state: "active".into(),
        };
        assert_eq!(scoped_udp_endpoint(&path).unwrap(), "[fe80::2%4]:4873");
    }

    #[tokio::test]
    async fn scoped_endpoint_is_accepted_by_system_resolution() {
        let resolved = tokio::net::lookup_host("[fe80::2%4]:4873")
            .await
            .unwrap()
            .next()
            .unwrap();
        let std::net::SocketAddr::V6(resolved) = resolved else {
            panic!("expected IPv6 endpoint");
        };
        assert_eq!(resolved.scope_id(), 4);
        assert_eq!(resolved.port(), 4873);
    }

    #[tokio::test]
    async fn aware_path_is_injected_into_fips_udp() {
        let dm_listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let dm_address = dm_listener.local_addr().unwrap();
        let dm = tokio::spawn(async move {
            axum::serve(
                dm_listener,
                Router::new().route(
                    "/network/wifi/aware/data-paths",
                    post(|| async {
                        Json(json!({
                            "id": "nan-path-1",
                            "match_id": "match-1",
                            "interface": "aware_data0",
                            "peer_address": "peer-handle",
                            "local_ipv6": "fe80::1%4",
                            "peer_ipv6": "fe80::2%4",
                            "port": 4873,
                            "state": "active"
                        }))
                    }),
                ),
            )
            .await
            .unwrap();
        });

        let directory = tempfile::tempdir().unwrap();
        let socket = directory.path().join("control.sock");
        let listener = UnixListener::bind(&socket).unwrap();
        let (request_tx, request_rx) = oneshot::channel();
        let fips = tokio::spawn(async move {
            let (stream, _) = listener.accept().await.unwrap();
            let (reader, mut writer) = stream.into_split();
            let mut request = String::new();
            BufReader::new(reader)
                .read_line(&mut request)
                .await
                .unwrap();
            request_tx
                .send(serde_json::from_str::<Value>(&request).unwrap())
                .unwrap();
            writer
                .write_all(b"{\"status\":\"ok\",\"data\":{}}\n")
                .await
                .unwrap();
        });

        let manager =
            TransportManager::with_fips_socket(format!("http://{dm_address}"), socket).unwrap();
        let path = manager
            .create_aware_path("npub1peer", "match-1", 4873)
            .await
            .unwrap();
        assert_eq!(path.id, "nan-path-1");
        let request = request_rx.await.unwrap();
        assert_eq!(request["params"]["npub"], "npub1peer");
        assert_eq!(request["params"]["address"], "[fe80::2%4]:4873");
        assert_eq!(request["params"]["transport"], "udp");
        fips.await.unwrap();
        dm.abort();
    }

    #[tokio::test]
    async fn coc_connection_is_handed_off_by_identifier() {
        let dm_listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let dm_address = dm_listener.local_addr().unwrap();
        let dm = tokio::spawn(async move {
            axum::serve(
                dm_listener,
                Router::new()
                    .route(
                        "/network/bluetooth/l2cap/connections",
                        post(|| async {
                            Json(json!({
                                "id": "l2cap-1",
                                "peer_address": "AA:BB:CC:DD:EE:FF",
                                "address_type": "public",
                                "psm": 129,
                                "mtu": 1024,
                                "handed_off": false
                            }))
                        }),
                    )
                    .route(
                        "/network/bluetooth/l2cap/connections/l2cap-1/fips-handoff",
                        post(|| async { Json(json!({"success": true})) }),
                    ),
            )
            .await
            .unwrap();
        });

        let manager = TransportManager::with_fips_socket(
            format!("http://{dm_address}"),
            PathBuf::from("/unused"),
        )
        .unwrap();
        let connection = manager
            .connect_coc("npub1peer", "AA:BB:CC:DD:EE:FF", 129, 1024, "public")
            .await
            .unwrap();
        assert_eq!(connection.id, "l2cap-1");
        assert!(connection.handed_off);
        dm.abort();
    }
}
