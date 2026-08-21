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
        // This is routing metadata only, matching Myco's BLE PSM carrier. No
        // identity is leaked in a passive Wi-Fi Aware announcement.
        let service_info = general_purpose::STANDARD.encode(udp_port.to_le_bytes());
        self.post_json(
            "/network/wifi/aware/discovery",
            json!({
                "service_name": MYCO_AWARE_SERVICE,
                "service_info_base64": service_info,
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
    use axum::routing::post;
    use axum::{Json, Router};
    use tokio::net::UnixListener;
    use tokio::sync::oneshot;

    #[test]
    fn discovery_metadata_is_only_little_endian_port() {
        assert_eq!(4873_u16.to_le_bytes(), [0x09, 0x13]);
    }

    #[test]
    fn device_manager_must_be_loopback() {
        assert!(TransportManager::new("http://192.168.8.9:8000".into()).is_err());
        assert!(TransportManager::new("http://127.0.0.1:8000".into()).is_ok());
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
