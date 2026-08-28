//! The two binds (`10-control-plane.md`): the public web port (static owner
//! app / JSON API / challenge endpoint) and the loopback-only bus. Ports are
//! pinned in `07-conventions.md`; bind addresses remain env-overridable.

use std::{
    convert::Infallible,
    net::SocketAddr,
    sync::{Arc, RwLock},
};

use axum::{
    extract::{DefaultBodyLimit, State},
    http::{header, uri::Authority, HeaderMap, StatusCode},
    response::{
        sse::{Event, KeepAlive, Sse},
        Html, IntoResponse, Response,
    },
    routing::{get, post},
    Json, Router,
};
use serde_json::{json, Value};
use tokio_stream::{wrappers::BroadcastStream, StreamExt};

use crate::{
    auth, bus, challenge,
    config::{self, Befriend},
    fips, owner, profile, relay,
    state::AppState,
    sync,
};

#[derive(Clone)]
struct ControlState {
    app: Arc<AppState>,
    signer: Arc<challenge::Signer>,
    profile: Arc<RwLock<profile::Profile>>,
}

fn addr_from_env(var: &str, default: &str) -> SocketAddr {
    let value = std::env::var_os(var).unwrap_or_else(|| default.into());
    let value = value
        .to_str()
        .unwrap_or_else(|| panic!("{var} must be UTF-8"));
    value
        .parse()
        .unwrap_or_else(|e| panic!("invalid {var}={value}: {e}"))
}

pub async fn serve() {
    let cfg = match config::Config::load(&config::Config::path()) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("totemd: {e}");
            std::process::exit(2);
        }
    };
    let st = match AppState::load(cfg, owner::path()) {
        Ok(state) => Arc::new(state),
        Err(e) => {
            eprintln!("totemd: {e}");
            std::process::exit(2);
        }
    };
    let cfg = st.config();
    tracing::info!(
        device_name = cfg.device_name,
        probe = cfg.probe,
        befriend = ?cfg.befriend,
        sync = cfg.sync,
        verdict_ttl_hours = cfg.verdict_ttl_hours,
        claimed = st.owner.owner().is_some(),
        "effective config"
    );
    let signer = match challenge::Signer::load(&challenge::key_path()) {
        Ok(signer) => Arc::new(signer),
        Err(e) => {
            eprintln!("totemd: {e}");
            std::process::exit(2);
        }
    };
    tracing::info!(pubkey = %signer.public_key().to_hex(), "device signing key loaded");
    let profile = Arc::new(RwLock::new(profile::reconcile(&cfg, signer.public_key())));
    let control = ControlState {
        app: st.clone(),
        signer: signer.clone(),
        profile,
    };

    // Loopback only: the bus is kernel-internal by construction.
    let bus_router = Router::new()
        .route("/bus", post(bus_post))
        .route("/bus/events", get(bus_events))
        .with_state(st.clone());
    // Public: static app, deliberately projected API, and challenge responder.
    let web_router = Router::new()
        .route("/", get(root))
        .route("/app.js", get(app_js))
        .route("/app.css", get(app_css))
        .route("/nsec-signer.js", get(nsec_signer_js))
        // The claim path a phone can actually walk. The wildcard is the return
        // leg: a NIP-55 signer appends its answer to the callback address, so
        // the signed event arrives as a path segment and this page has to be
        // served for whatever it turns out to be.
        // Short enough to read off a panel and type into a phone by hand.
        .route("/claim", get(phone_claim))
        .route("/claim/", get(phone_claim))
        .route("/claim/phone", get(phone_claim))
        // Both, because a wildcard needs at least one segment: the bare callback
        // address is what a signer hits if it appends nothing, and answering it
        // with 404 turns a recoverable moment into a dead end.
        .route("/claim/phone/", get(phone_claim))
        .route("/claim/phone/{*answer}", get(phone_claim))
        .route("/claim/phone.js", get(phone_claim_js))
        .route("/claim/phone.css", get(phone_claim_css))
        .route("/api/status", get(status_get))
        .route("/api/updates", get(web_updates))
        .route("/api/auth/challenge", post(auth_challenge))
        .route("/api/owner", get(owner_status))
        .route("/api/owner/claim", post(owner_claim))
        .route("/api/owner/events", get(owner_events))
        .route("/api/metadata", get(metadata_get).put(metadata_put))
        .route("/api/config", get(config_get).put(config_put))
        .layer(DefaultBodyLimit::max(64 * 1024))
        .with_state(control)
        .merge(challenge::router(signer));

    let web_addr = addr_from_env("TOTEMD_WEB_ADDR", "[::]:8080");
    let bus_addr = addr_from_env("TOTEMD_BUS_ADDR", "127.0.0.1:8081");
    let web_l = tokio::net::TcpListener::bind(web_addr)
        .await
        .expect("web bind");
    let bus_l = tokio::net::TcpListener::bind(bus_addr)
        .await
        .expect("bus bind");

    // Bind the responder before existing FIPS peers trigger challenges.
    let fips_task = tokio::spawn(fips::watch(st.clone()));
    let relay_task = tokio::spawn(relay::watch(st.clone()));

    tracing::info!(
        version = env!("CARGO_PKG_VERSION"),
        web = %web_addr,
        bus = %bus_addr,
        "totemd starting (bus loopback only)"
    );

    let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(false);
    let shutdown_st = st.clone();
    let fips_abort = fips_task.abort_handle();
    let relay_abort = relay_task.abort_handle();
    tokio::spawn(async move {
        shutdown_signal().await;
        fips_abort.abort();
        relay_abort.abort();
        sync::cancel_all(&shutdown_st);
        let _ = shutdown_tx.send(true);
    });
    let mut web_shutdown = shutdown_rx.clone();
    let mut bus_shutdown = shutdown_rx;
    let web = axum::serve(web_l, web_router).with_graceful_shutdown(async move {
        let _ = web_shutdown.changed().await;
    });
    let bus = axum::serve(bus_l, bus_router).with_graceful_shutdown(async move {
        let _ = bus_shutdown.changed().await;
    });
    let result = tokio::try_join!(web, bus);
    fips_task.abort();
    relay_task.abort();
    sync::shutdown(&st).await;
    result.expect("server failed");
    tracing::info!("totemd shut down");
}

async fn shutdown_signal() {
    #[cfg(unix)]
    {
        let mut terminate =
            tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
                .expect("SIGTERM handler");
        tokio::select! {
            _ = tokio::signal::ctrl_c() => {}
            _ = terminate.recv() => {}
        }
    }
    #[cfg(not(unix))]
    let _ = tokio::signal::ctrl_c().await;
}

type ApiFailure = (StatusCode, String);

fn base_url(headers: &HeaderMap) -> Result<String, ApiFailure> {
    let host = headers
        .get(header::HOST)
        .and_then(|value| value.to_str().ok())
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "missing Host header".into()))?;
    let authority = host
        .parse::<Authority>()
        .map_err(|_| (StatusCode::BAD_REQUEST, "invalid Host header".into()))?;
    Ok(format!("http://{authority}"))
}

fn api_json<T: serde::Serialize>(value: T) -> Response {
    ([(header::CACHE_CONTROL, "no-store")], Json(value)).into_response()
}

fn api_error(status: StatusCode, error: &str) -> Response {
    (
        status,
        [(header::CACHE_CONTROL, "no-store")],
        Json(json!({ "ok": false, "error": error })),
    )
        .into_response()
}

async fn auth_challenge(
    State(control): State<ControlState>,
    headers: HeaderMap,
    body: String,
) -> Response {
    let request: auth::ChallengeRequest = match serde_json::from_str(&body) {
        Ok(request) => request,
        Err(_) => return api_error(StatusCode::BAD_REQUEST, "invalid challenge request"),
    };
    let base = match base_url(&headers) {
        Ok(base) => base,
        Err((status, error)) => return api_error(status, &error),
    };
    match control.app.auth.issue(&base, request) {
        Ok(challenge) => api_json(challenge),
        Err(error) => api_error(StatusCode::BAD_REQUEST, &error),
    }
}

fn authorize(
    control: &ControlState,
    headers: &HeaderMap,
    path: &str,
    method: &str,
    body: &[u8],
) -> Result<nostr::prelude::PublicKey, ApiFailure> {
    let authorization = headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .ok_or_else(|| {
            (
                StatusCode::UNAUTHORIZED,
                "Nostr authorization required".into(),
            )
        })?;
    let url = format!("{}{path}", base_url(headers)?);
    control
        .app
        .auth
        .verify(authorization, &url, method, body)
        .map_err(|error| (StatusCode::UNAUTHORIZED, error))
}

fn authorize_owner(
    control: &ControlState,
    headers: &HeaderMap,
    path: &str,
    method: &str,
    body: &[u8],
) -> Result<(), ApiFailure> {
    let signer = authorize(control, headers, path, method, body)?;
    if control.app.owner.owner() == Some(signer) {
        Ok(())
    } else {
        Err((StatusCode::FORBIDDEN, "owner signature required".into()))
    }
}

async fn owner_status(State(control): State<ControlState>) -> Response {
    api_json(json!({ "claimed": control.app.owner.owner().is_some() }))
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct EmptyRequest {}

async fn owner_claim(
    State(control): State<ControlState>,
    headers: HeaderMap,
    body: String,
) -> Response {
    if control.app.owner.owner().is_some() {
        return api_error(StatusCode::CONFLICT, "totem is already claimed");
    }
    let signer = match authorize(
        &control,
        &headers,
        "/api/owner/claim",
        "POST",
        body.as_bytes(),
    ) {
        Ok(signer) => signer,
        Err((status, error)) => return api_error(status, &error),
    };
    if serde_json::from_str::<EmptyRequest>(&body).is_err() {
        return api_error(
            StatusCode::BAD_REQUEST,
            "claim body must be an empty object",
        );
    }
    match control.app.owner.claim(signer) {
        Ok(true) => {
            tracing::info!(owner = %signer.to_hex(), "totem claimed");
            control.app.push(json!({ "type": "totem.owner.claimed" }));
            api_json(json!({ "ok": true, "claimed": true }))
        }
        Ok(false) => api_error(StatusCode::CONFLICT, "totem is already claimed"),
        Err(error) => {
            tracing::error!(%error, "persisting owner claim failed");
            api_error(StatusCode::INTERNAL_SERVER_ERROR, "owner claim failed")
        }
    }
}

async fn metadata_get(State(control): State<ControlState>) -> Response {
    api_json(control.profile.read().unwrap().clone())
}

async fn metadata_put(
    State(control): State<ControlState>,
    headers: HeaderMap,
    body: String,
) -> Response {
    if let Err((status, error)) =
        authorize_owner(&control, &headers, "/api/metadata", "PUT", body.as_bytes())
    {
        return api_error(status, &error);
    }
    let metadata = match serde_json::from_str(&body)
        .map_err(|_| "invalid metadata".to_string())
        .and_then(profile::validate)
    {
        Ok(metadata) => metadata,
        Err(error) => return api_error(StatusCode::BAD_REQUEST, &error),
    };
    let signer = control.signer.clone();
    let result = tokio::task::spawn_blocking(move || profile::publish(&signer, metadata)).await;
    let (profile, event) = match result {
        Ok(Ok(result)) => result,
        Ok(Err(error)) => {
            tracing::error!(%error, "publishing device metadata failed");
            return api_error(StatusCode::INTERNAL_SERVER_ERROR, "metadata publish failed");
        }
        Err(error) => {
            tracing::error!(%error, "metadata task failed");
            return api_error(StatusCode::INTERNAL_SERVER_ERROR, "metadata publish failed");
        }
    };
    *control.profile.write().unwrap() = profile.clone();
    control.app.push(json!({
        "type": "totem.metadata.changed",
        "event_id": event.id.to_hex(),
        "name": profile.metadata.name,
    }));
    api_json(json!({ "ok": true, "profile": profile, "event_id": event.id.to_hex() }))
}

async fn config_get(State(control): State<ControlState>) -> Response {
    api_json(control.app.config())
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct ConfigUpdate {
    sync: bool,
    befriend: Befriend,
}

async fn config_put(
    State(control): State<ControlState>,
    headers: HeaderMap,
    body: String,
) -> Response {
    if let Err((status, error)) =
        authorize_owner(&control, &headers, "/api/config", "PUT", body.as_bytes())
    {
        return api_error(status, &error);
    }
    let update: ConfigUpdate = match serde_json::from_str(&body) {
        Ok(update) => update,
        Err(_) => return api_error(StatusCode::BAD_REQUEST, "invalid configuration"),
    };
    match control.app.update_policy(update.sync, update.befriend) {
        Ok(config) => api_json(json!({ "ok": true, "config": config })),
        Err(error) => {
            tracing::error!(%error, "persisting owner configuration failed");
            api_error(
                StatusCode::INTERNAL_SERVER_ERROR,
                "configuration update failed",
            )
        }
    }
}

fn status_value(app: &AppState) -> Value {
    bus::handle(json!({"type": "totem.status.get"}), app)["status"].clone()
}

fn relay_url(host: &str) -> Option<String> {
    host.parse::<Authority>()
        .ok()
        .map(|authority| format!("ws://{}:7777", authority.host()))
}

fn public_snapshot(app: &AppState, profile: &profile::Profile, relay: &str) -> Value {
    json!({
        "status": status_value(app),
        "profile": profile,
        "relay_url": relay,
    })
}

async fn status_get(State(control): State<ControlState>, headers: HeaderMap) -> Response {
    let relay = headers
        .get(header::HOST)
        .and_then(|value| value.to_str().ok())
        .and_then(relay_url)
        .unwrap_or_else(|| "ws://this-totem:7777".into());
    api_json(public_snapshot(
        &control.app,
        &control.profile.read().unwrap(),
        &relay,
    ))
}

fn owner_snapshot(app: &AppState) -> Value {
    json!({
        "status": status_value(app),
        "peers": app.peers_snapshot(),
        "events": app.event_history(),
    })
}

fn owner_update(app: &AppState, event: Value) -> Value {
    json!({
        "status": status_value(app),
        "peers": app.peers_snapshot(),
        "event": event,
    })
}

/// One owner signature authenticates the long-lived current-state/history
/// snapshot and future-only stream. Reconnection requires a fresh signature.
async fn owner_events(State(control): State<ControlState>, headers: HeaderMap) -> Response {
    if let Err((status, error)) =
        authorize_owner(&control, &headers, "/api/owner/events", "GET", b"")
    {
        return api_error(status, &error);
    }

    // Subscribe first: an event racing the snapshot may be duplicated, never lost.
    let receiver = control.app.tx.subscribe();
    let initial = Ok::<_, Infallible>(
        Event::default()
            .event("snapshot")
            .data(owner_snapshot(&control.app).to_string()),
    );
    let live_app = control.app.clone();
    let live = BroadcastStream::new(receiver)
        .filter_map(|message| message.ok())
        .map(move |event| {
            Ok::<_, Infallible>(
                Event::default()
                    .event("update")
                    .data(owner_update(&live_app, event).to_string()),
            )
        });
    (
        [
            (header::CACHE_CONTROL, "no-store"),
            (header::X_CONTENT_TYPE_OPTIONS, "nosniff"),
        ],
        Sse::new(tokio_stream::once(initial).chain(live)).keep_alive(KeepAlive::default()),
    )
        .into_response()
}

/// Public updates carry no peer payload; clients use them only to invalidate
/// and refetch the deliberately limited `/api/status` projection.
async fn web_updates(
    State(control): State<ControlState>,
) -> Sse<impl tokio_stream::Stream<Item = Result<Event, Infallible>>> {
    let stream = BroadcastStream::new(control.app.tx.subscribe())
        .filter_map(|message| message.ok())
        .map(|_| Ok::<_, Infallible>(Event::default().event("update").data("{}")));
    Sse::new(stream).keep_alive(KeepAlive::default())
}

const INDEX_HTML: &str = include_str!("../web/static/index.html");
const APP_JS: &str = include_str!("../web/static/app.js");
const APP_CSS: &str = include_str!("../web/static/app.css");
const NSEC_SIGNER_JS: &str = include_str!("../web/nsec-signer.js");
const PHONE_CLAIM_HTML: &str = include_str!("../web/phone-claim.html");
const PHONE_CLAIM_JS: &str = include_str!("../web/phone-claim.js");
const PHONE_CLAIM_CSS: &str = include_str!("../web/phone-claim.css");

fn text_asset(content_type: &'static str, source: &'static str) -> Response {
    (
        [
            (header::CACHE_CONTROL, "no-store"),
            (header::CONTENT_TYPE, content_type),
            (header::X_CONTENT_TYPE_OPTIONS, "nosniff"),
        ],
        source,
    )
        .into_response()
}

async fn app_js() -> Response {
    text_asset("text/javascript; charset=utf-8", APP_JS)
}

async fn app_css() -> Response {
    text_asset("text/css; charset=utf-8", APP_CSS)
}

async fn nsec_signer_js() -> Response {
    text_asset("text/javascript; charset=utf-8", NSEC_SIGNER_JS)
}

async fn phone_claim_js() -> Response {
    text_asset("text/javascript; charset=utf-8", PHONE_CLAIM_JS)
}

async fn phone_claim_css() -> Response {
    text_asset("text/css; charset=utf-8", PHONE_CLAIM_CSS)
}

/// The claim page a phone loads over this device's own access point.
///
/// Narrower than the app shell's policy: this page talks to no extension and
/// loads nothing but its own two assets. Navigating to the `nostrsigner:` link
/// is untouched by any of these directives - `form-action` governs forms, and
/// `navigate-to` was never shipped - so the hand-off to the signer app is not
/// something a stricter policy here can break.
async fn phone_claim() -> Response {
    (
        [
            (header::CACHE_CONTROL, "no-store"),
            (
                header::CONTENT_SECURITY_POLICY,
                "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            ),
            (header::X_CONTENT_TYPE_OPTIONS, "nosniff"),
        ],
        Html(PHONE_CLAIM_HTML),
    )
        .into_response()
}

async fn root() -> Response {
    (
        [
            (header::CACHE_CONTROL, "no-store"),
            (
                header::CONTENT_SECURITY_POLICY,
                "default-src 'none'; script-src 'self' chrome-extension: moz-extension:; connect-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            ),
            (header::X_CONTENT_TYPE_OPTIONS, "nosniff"),
        ],
        Html(INDEX_HTML),
    )
        .into_response()
}

async fn bus_post(State(st): State<Arc<AppState>>, body: String) -> Json<Value> {
    let msg: Value = match serde_json::from_str::<Value>(&body) {
        Ok(v) if v.is_object() => v,
        _ => {
            return Json(json!({"ok": false, "error": "message must be a JSON object"}));
        }
    };
    Json(bus::handle(msg, &st))
}

/// SSE stream of unsolicited pushes; lossy — lagged messages are skipped
/// and consumers reconcile via `totem.status.get` (`07-conventions.md`).
async fn bus_events(
    State(st): State<Arc<AppState>>,
) -> Sse<impl tokio_stream::Stream<Item = Result<Event, Infallible>>> {
    let stream = BroadcastStream::new(st.tx.subscribe())
        .filter_map(|m| m.ok())
        .map(|v| {
            let name = v.get("type").and_then(Value::as_str).unwrap_or("message");
            Ok::<_, Infallible>(Event::default().event(name).data(v.to_string()))
        });
    Sse::new(stream).keep_alive(KeepAlive::default())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relay_url_uses_the_request_host() {
        assert_eq!(
            relay_url("totem.local:8080").as_deref(),
            Some("ws://totem.local:7777")
        );
        assert_eq!(
            relay_url("[fd00::1]:8080").as_deref(),
            Some("ws://[fd00::1]:7777")
        );
        assert!(relay_url("bad host").is_none());
    }

    #[test]
    fn static_index_has_only_external_application_assets() {
        assert!(INDEX_HTML.starts_with("<!doctype html>"));
        assert!(INDEX_HTML.contains("src=\"/app.js\""));
        assert!(APP_JS.contains("/nsec-signer.js"));
        assert!(INDEX_HTML.contains("href=\"/app.css\""));
        assert!(!INDEX_HTML.contains("<style>"));
    }

    #[test]
    fn public_and_owner_snapshots_project_existing_state() {
        let app = AppState::new(config::Config::default());
        app.push(json!({"type": "totem.test", "value": 1}));
        let profile = profile::Profile {
            metadata: profile::DeviceMetadata {
                name: "test".into(),
                display_name: None,
                about: None,
                picture: None,
                website: None,
            },
            source: "config",
            nip11_name: "!Totem test".into(),
        };
        let public = public_snapshot(&app, &profile, "ws://totem:7777");
        assert_eq!(public["profile"]["name"], "test");
        assert_eq!(public["relay_url"], "ws://totem:7777");
        assert_eq!(public["status"]["events"]["totem.test"], 1);

        let owner = owner_snapshot(&app);
        assert_eq!(owner["events"][0]["type"], "totem.test");
        assert!(owner["peers"].as_array().unwrap().is_empty());
    }
}
