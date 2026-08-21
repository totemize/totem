use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use serde_json::json;

mod app;
mod model;
mod protocol;
mod server;
mod transport;

const HELP: &str = "totem-myco — Myco-compatible Totem integration

Usage:
  totem-myco serve
  totem-myco status
  totem-myco invite
  totem-myco pair <myco://pair/...>
  totem-myco accept-pair <npub>
  totem-myco decline-pair <npub>
  totem-myco unpair <npub>
  totem-myco send <peer-npub> <path> [mime]
  totem-myco accept-file <transfer-id>
  totem-myco decline-file <transfer-id>
  totem-myco transports
  totem-myco route <peer-npub> <lan|softap> <udp-endpoint>
  totem-myco unroute <peer-npub> <lan|softap>
  totem-myco aware-discover [udp-port] [seconds]
  totem-myco aware-connect <peer-npub> <match-id> [udp-port]
  totem-myco aware-remove <data-path-id>
  totem-myco coc-connect <peer-npub> <bluetooth-address> <psm> [public|random]";

#[tokio::main]
async fn main() {
    if let Err(error) = run().await {
        eprintln!("totem-myco: {error:#}");
        std::process::exit(1);
    }
}

async fn run() -> Result<()> {
    let mut args = std::env::args().skip(1);
    let command = args.next().unwrap_or_else(|| "help".to_string());
    match command.as_str() {
        "serve" => serve().await,
        "status" => print_response(get("/state").await?),
        "invite" => print_response(post("/invite", None).await?),
        "pair" => {
            let uri = required(args.next(), "pair URI")?;
            print_response(post("/pair", Some(json!({"uri": uri}))).await?)
        }
        "accept-pair" => {
            let npub = required(args.next(), "npub")?;
            print_response(post(&format!("/pairs/{npub}/accept"), None).await?)
        }
        "decline-pair" => {
            let npub = required(args.next(), "npub")?;
            print_response(post(&format!("/pairs/{npub}/decline"), None).await?)
        }
        "unpair" => {
            let npub = required(args.next(), "npub")?;
            print_response(delete(&format!("/pairs/{npub}")).await?)
        }
        "send" => {
            let npub = required(args.next(), "peer npub")?;
            let path = required(args.next(), "file path")?;
            let mime = args.next();
            let name = Path::new(&path)
                .file_name()
                .and_then(|v| v.to_str())
                .unwrap_or("shared-file");
            print_response(
                post(
                    "/files",
                    Some(json!({
                        "peerNpub": npub,
                        "path": path,
                        "name": name,
                        "mime": mime.unwrap_or_else(|| "application/octet-stream".into())
                    })),
                )
                .await?,
            )
        }
        "accept-file" => {
            let id = required(args.next(), "transfer id")?;
            print_response(post(&format!("/files/{id}/accept"), None).await?)
        }
        "decline-file" => {
            let id = required(args.next(), "transfer id")?;
            print_response(post(&format!("/files/{id}/decline"), None).await?)
        }
        "transports" => print_response(get("/transports").await?),
        "route" => {
            let npub = required(args.next(), "peer npub")?;
            let transport = required(args.next(), "lan or softap")?;
            let address = required(args.next(), "peer UDP endpoint")?;
            print_response(
                post(
                    "/transports/routes",
                    Some(json!({
                        "peerNpub": npub,
                        "transport": transport,
                        "address": address,
                    })),
                )
                .await?,
            )
        }
        "unroute" => {
            let npub = required(args.next(), "peer npub")?;
            let transport = required(args.next(), "lan or softap")?;
            print_response(delete(&format!("/transports/routes/{npub}/{transport}")).await?)
        }
        "aware-discover" => {
            let port = optional_u16(args.next(), "UDP port")?.unwrap_or(4873);
            let seconds = optional_u16(args.next(), "duration")?.unwrap_or(300);
            print_response(
                post(
                    "/transports/aware/discovery",
                    Some(json!({"udpPort": port, "durationSeconds": seconds})),
                )
                .await?,
            )
        }
        "aware-connect" => {
            let npub = required(args.next(), "peer npub")?;
            let match_id = required(args.next(), "match id")?;
            let port = optional_u16(args.next(), "UDP port")?.unwrap_or(4873);
            print_response(
                post(
                    "/transports/aware/data-paths",
                    Some(json!({"peerNpub": npub, "matchId": match_id, "port": port})),
                )
                .await?,
            )
        }
        "aware-remove" => {
            let id = required(args.next(), "data path id")?;
            print_response(delete(&format!("/transports/aware/data-paths/{id}")).await?)
        }
        "coc-connect" => {
            let npub = required(args.next(), "peer npub")?;
            let peer_address = required(args.next(), "Bluetooth address")?;
            let psm = optional_u16(args.next(), "PSM")?.context("missing PSM")?;
            let address_type = args.next().unwrap_or_else(|| "public".into());
            print_response(
                post(
                    "/transports/coc",
                    Some(json!({
                        "peerNpub": npub,
                        "peerAddress": peer_address,
                        "psm": psm,
                        "addressType": address_type,
                    })),
                )
                .await?,
            )
        }
        "version" | "-V" | "--version" => {
            println!("totem-myco {}", env!("CARGO_PKG_VERSION"));
            Ok(())
        }
        "help" | "-h" | "--help" => {
            println!("{HELP}");
            Ok(())
        }
        other => bail!("unknown command {other:?}\n\n{HELP}"),
    }
}

async fn serve() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("totem_myco=info".parse().unwrap()),
        )
        .init();
    let data_dir = PathBuf::from(
        std::env::var("TOTEM_MYCO_DATA_DIR").unwrap_or_else(|_| "/var/lib/totem-myco".into()),
    );
    let credential = credential_path();
    let name = std::env::var("TOTEM_MYCO_NAME").unwrap_or_else(|_| "Totem".into());
    let app = app::App::open(&data_dir, &credential, &name)?;
    tracing::info!(npub = %app.npub(), data_dir = %app.data_dir().display(), "starting Myco integration");
    server::serve(app).await
}

fn credential_path() -> PathBuf {
    if let Ok(path) = std::env::var("TOTEM_MYCO_KEY") {
        return PathBuf::from(path);
    }
    if let Ok(directory) = std::env::var("CREDENTIALS_DIRECTORY") {
        return PathBuf::from(directory).join("fips.key");
    }
    PathBuf::from("/etc/fips/fips.key")
}

fn required(value: Option<String>, name: &str) -> Result<String> {
    value.with_context(|| format!("missing {name}"))
}

fn optional_u16(value: Option<String>, name: &str) -> Result<Option<u16>> {
    value
        .map(|value| value.parse().with_context(|| format!("invalid {name}")))
        .transpose()
}

async fn get(path: &str) -> Result<serde_json::Value> {
    request(reqwest::Method::GET, path, None).await
}

async fn post(path: &str, body: Option<serde_json::Value>) -> Result<serde_json::Value> {
    request(reqwest::Method::POST, path, body).await
}

async fn delete(path: &str) -> Result<serde_json::Value> {
    request(reqwest::Method::DELETE, path, None).await
}

async fn request(
    method: reqwest::Method,
    path: &str,
    body: Option<serde_json::Value>,
) -> Result<serde_json::Value> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(130))
        .build()?;
    let mut request = client.request(method, format!("http://127.0.0.1:4874{path}"));
    if let Some(body) = body {
        request = request.json(&body);
    }
    let response = request
        .send()
        .await
        .context("connect to Myco integration")?;
    let status = response.status();
    let bytes = response.bytes().await?;
    let value: serde_json::Value = serde_json::from_slice(&bytes).with_context(|| {
        format!(
            "integration returned {status}: {}",
            String::from_utf8_lossy(&bytes)
        )
    })?;
    if !status.is_success() {
        bail!("integration returned {status}: {value}");
    }
    Ok(value)
}

fn print_response(value: serde_json::Value) -> Result<()> {
    println!("{}", serde_json::to_string_pretty(&value)?);
    Ok(())
}
