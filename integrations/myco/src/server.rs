use std::net::{IpAddr, SocketAddr};
use std::path::PathBuf;
use std::sync::Arc;

use axum::body::Body;
use axum::extract::ws::{Message, WebSocket};
use axum::extract::{ConnectInfo, DefaultBodyLimit, Path, State, WebSocketUpgrade};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use futures_util::StreamExt;
use nostr::prelude::Event;
use serde::Deserialize;

use crate::app::App;

pub async fn serve(app: Arc<App>) -> anyhow::Result<()> {
    let auth = Router::new()
        .route("/pair", post(pair))
        .layer(DefaultBodyLimit::max(128 * 1024))
        .with_state(app.clone());
    let relay = Router::new()
        .route("/", get(relay_upgrade))
        .with_state(app.clone());
    let blossom = Router::new()
        .route("/{hash}", get(blob_get))
        .with_state(app.clone());
    let control = Router::new()
        .route("/state", get(control_state))
        .route("/invite", post(control_invite))
        .route("/pair", post(control_pair))
        .route("/pairs/{npub}/accept", post(control_pair_accept))
        .route("/pairs/{npub}/decline", post(control_pair_decline))
        .route("/pairs/{npub}", axum::routing::delete(control_unpair))
        .route("/files", post(control_file_send))
        .route("/files/{id}/accept", post(control_file_accept))
        .route("/files/{id}/decline", post(control_file_decline))
        .route("/transports", get(control_transports))
        .route("/transports/routes", post(control_route_register))
        .route(
            "/transports/routes/{npub}/{kind}",
            axum::routing::delete(control_route_remove),
        )
        .route("/transports/aware/discovery", post(control_aware_discovery))
        .route(
            "/transports/aware/data-paths",
            post(control_aware_data_path),
        )
        .route(
            "/transports/aware/data-paths/{id}",
            axum::routing::delete(control_aware_data_path_remove),
        )
        .route("/transports/coc", post(control_coc_connect))
        .layer(DefaultBodyLimit::max(128 * 1024))
        .with_state(app);

    let auth_listener = ipv6_listener(4873).await?;
    let relay_listener = ipv6_listener(4870).await?;
    let blossom_listener = ipv6_listener(24243).await?;
    let control_listener = tokio::net::TcpListener::bind("127.0.0.1:4874").await?;
    tracing::info!("Myco pairing listening on [::]:4873");
    tracing::info!("Myco file control listening on [::]:4870");
    tracing::info!("Myco encrypted blobs listening on [::]:24243");
    tracing::info!("Myco integration control listening on 127.0.0.1:4874");

    let tasks = vec![
        tokio::spawn(async move {
            axum::serve(
                auth_listener,
                auth.into_make_service_with_connect_info::<SocketAddr>(),
            )
            .await
        }),
        tokio::spawn(async move {
            axum::serve(
                relay_listener,
                relay.into_make_service_with_connect_info::<SocketAddr>(),
            )
            .await
        }),
        tokio::spawn(async move {
            axum::serve(
                blossom_listener,
                blossom.into_make_service_with_connect_info::<SocketAddr>(),
            )
            .await
        }),
        tokio::spawn(async move { axum::serve(control_listener, control).await }),
    ];
    tokio::signal::ctrl_c().await?;
    for task in tasks {
        task.abort();
    }
    Ok(())
}

async fn ipv6_listener(port: u16) -> anyhow::Result<tokio::net::TcpListener> {
    let socket = tokio::net::TcpSocket::new_v6()?;
    socket.set_reuseaddr(true)?;
    socket.bind(SocketAddr::new(
        IpAddr::V6(std::net::Ipv6Addr::UNSPECIFIED),
        port,
    ))?;
    Ok(socket.listen(128)?)
}

async fn pair(State(app): State<Arc<App>>, body: String) -> Response {
    let event = match serde_json::from_str::<Event>(&body) {
        Ok(event) => event,
        Err(_) => return error(StatusCode::BAD_REQUEST, "malformed pairing event"),
    };
    match app.handle_pair_event(&event) {
        Ok(status) => {
            let code = if status == "pending" {
                StatusCode::ACCEPTED
            } else {
                StatusCode::OK
            };
            (code, Json(serde_json::json!({"status": status}))).into_response()
        }
        Err(e) => error(StatusCode::FORBIDDEN, &e.to_string()),
    }
}

async fn relay_upgrade(
    State(app): State<Arc<App>>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    ws: WebSocketUpgrade,
) -> Response {
    let IpAddr::V6(ip) = peer.ip() else {
        return error(StatusCode::FORBIDDEN, "Myco relay is mesh-only");
    };
    if app.circle_npub_for_ip(ip).is_none() {
        return error(StatusCode::FORBIDDEN, "peer is not in the Circle");
    }
    ws.on_upgrade(move |socket| relay_session(app, socket))
}

async fn relay_session(app: Arc<App>, mut socket: WebSocket) {
    while let Some(message) = socket.next().await {
        let Ok(Message::Text(text)) = message else {
            continue;
        };
        match app.handle_mesh_frame(&text).await {
            Ok(event) => {
                let reply = serde_json::json!(["OK", event.id.to_hex(), true, ""]).to_string();
                if socket.send(Message::Text(reply.into())).await.is_err() {
                    break;
                }
            }
            Err(e) => {
                tracing::warn!(error = %e, "refused Myco relay frame");
                let reply = serde_json::json!(["NOTICE", e.to_string()]).to_string();
                if socket.send(Message::Text(reply.into())).await.is_err() {
                    break;
                }
            }
        }
    }
}

async fn blob_get(
    State(app): State<Arc<App>>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    Path(hash): Path<String>,
) -> Response {
    let IpAddr::V6(ip) = peer.ip() else {
        return error(StatusCode::FORBIDDEN, "Myco Blossom is mesh-only");
    };
    if app.circle_npub_for_ip(ip).is_none() {
        return error(StatusCode::FORBIDDEN, "peer is not in the Circle");
    }
    match app.blob(&hash).await {
        Ok(bytes) => Response::builder()
            .status(StatusCode::OK)
            .header(header::CONTENT_TYPE, "application/octet-stream")
            .header(header::CONTENT_LENGTH, bytes.len())
            .body(Body::from(bytes))
            .unwrap(),
        Err(_) => error(StatusCode::NOT_FOUND, "blob not found"),
    }
}

async fn control_state(State(app): State<Arc<App>>) -> Json<crate::model::PublicState> {
    Json(app.public_state())
}

async fn control_transports(
    State(app): State<Arc<App>>,
) -> Json<crate::transport::TransportStatus> {
    Json(app.transport_status().await)
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct DirectRouteInput {
    peer_npub: String,
    address: String,
    transport: String,
}

async fn control_route_register(
    State(app): State<Arc<App>>,
    Json(input): Json<DirectRouteInput>,
) -> Response {
    match app
        .connect_udp_lane(&input.peer_npub, &input.address, &input.transport)
        .await
    {
        Ok(route) => Json(route).into_response(),
        Err(e) => error(StatusCode::BAD_REQUEST, &e.to_string()),
    }
}

async fn control_route_remove(
    State(app): State<Arc<App>>,
    Path((npub, kind)): Path<(String, String)>,
) -> Response {
    match app.remove_udp_lane(&npub, &kind) {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(e) => error(StatusCode::BAD_REQUEST, &e.to_string()),
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct AwareDiscoveryInput {
    duration_seconds: Option<u16>,
    udp_port: Option<u16>,
}

async fn control_aware_discovery(
    State(app): State<Arc<App>>,
    Json(input): Json<AwareDiscoveryInput>,
) -> Response {
    match app
        .start_aware_discovery(
            input.udp_port.unwrap_or(4873),
            input.duration_seconds.unwrap_or(300).clamp(1, 3600),
        )
        .await
    {
        Ok(session) => Json(session).into_response(),
        Err(e) => error(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct AwareDataPathInput {
    peer_npub: String,
    match_id: String,
    port: Option<u16>,
}

async fn control_aware_data_path(
    State(app): State<Arc<App>>,
    Json(input): Json<AwareDataPathInput>,
) -> Response {
    match app
        .create_aware_path(
            &input.peer_npub,
            &input.match_id,
            input.port.unwrap_or(4873),
        )
        .await
    {
        Ok(path) => Json(path).into_response(),
        Err(e) => error(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

async fn control_aware_data_path_remove(
    State(app): State<Arc<App>>,
    Path(id): Path<String>,
) -> Response {
    match app.remove_aware_path(&id).await {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(e) => error(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct CocInput {
    peer_npub: String,
    peer_address: String,
    psm: u16,
    mtu: Option<u16>,
    address_type: Option<String>,
}

async fn control_coc_connect(State(app): State<Arc<App>>, Json(input): Json<CocInput>) -> Response {
    match app
        .connect_coc(
            &input.peer_npub,
            &input.peer_address,
            input.psm,
            input.mtu.unwrap_or(1024),
            input.address_type.as_deref().unwrap_or("public"),
        )
        .await
    {
        Ok(connection) => Json(connection).into_response(),
        Err(e) => error(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

async fn control_invite(State(app): State<Arc<App>>) -> Response {
    match app.create_invite() {
        Ok(uri) => Json(serde_json::json!({"uri": uri})).into_response(),
        Err(e) => internal(e),
    }
}

#[derive(Deserialize)]
struct PairInput {
    uri: String,
}

async fn control_pair(State(app): State<Arc<App>>, Json(input): Json<PairInput>) -> Response {
    match app.pair_from_uri(&input.uri).await {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(e) => error(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

async fn control_pair_accept(State(app): State<Arc<App>>, Path(npub): Path<String>) -> Response {
    match app.accept_pair(&npub).await {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(e) => error(StatusCode::BAD_REQUEST, &e.to_string()),
    }
}

async fn control_pair_decline(State(app): State<Arc<App>>, Path(npub): Path<String>) -> Response {
    match app.decline_pair(&npub) {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(e) => internal(e),
    }
}

async fn control_unpair(State(app): State<Arc<App>>, Path(npub): Path<String>) -> Response {
    match app.unpair(&npub).await {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(e) => error(StatusCode::BAD_GATEWAY, &e.to_string()),
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct FileInput {
    path: PathBuf,
    peer_npub: String,
    name: Option<String>,
    mime: Option<String>,
}

async fn control_file_send(State(app): State<Arc<App>>, Json(input): Json<FileInput>) -> Response {
    match app
        .share_file(
            &input.path,
            &input.peer_npub,
            input.name.as_deref(),
            input.mime.as_deref(),
        )
        .await
    {
        Ok(id) => Json(serde_json::json!({"ok": true, "transferId": id})).into_response(),
        Err(e) => error(StatusCode::BAD_REQUEST, &e.to_string()),
    }
}

async fn control_file_accept(State(app): State<Arc<App>>, Path(id): Path<String>) -> Response {
    match app.respond_file(&id, true).await {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(e) => error(StatusCode::BAD_REQUEST, &e.to_string()),
    }
}

async fn control_file_decline(State(app): State<Arc<App>>, Path(id): Path<String>) -> Response {
    match app.respond_file(&id, false).await {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(e) => error(StatusCode::BAD_REQUEST, &e.to_string()),
    }
}

fn internal(error_value: anyhow::Error) -> Response {
    tracing::error!(error = %error_value, "Myco integration request failed");
    error(StatusCode::INTERNAL_SERVER_ERROR, "internal error")
}

fn error(status: StatusCode, message: &str) -> Response {
    (status, Json(serde_json::json!({"error": message}))).into_response()
}
