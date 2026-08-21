//! The two binds (`10-control-plane.md`): the public web port (guest page /
//! owner app / challenge endpoint) and the loopback-only bus. Ports are
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
    // Public: guest page, owner API, and the signed challenge responder.
    let web_router = Router::new()
        .route("/", get(root))
        .route("/app.js", get(app_js))
        .route("/nsec-signer.js", get(nsec_signer_js))
        .route("/api/auth/challenge", post(auth_challenge))
        .route("/api/owner", get(owner_status))
        .route("/api/owner/claim", post(owner_claim))
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

const STYLE: &str = r#"
:root { color-scheme: light dark; font-family: ui-sans-serif, system-ui, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: #f4efe5; color: #20251f; }
main { width: min(44rem, calc(100% - 2rem)); margin: 0 auto; padding: 4rem 0; }
header { margin-bottom: 2rem; }
.eyebrow { margin: 0; color: #5c6758; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
h1 { margin: .25rem 0; font-size: clamp(2.5rem, 10vw, 5rem); line-height: 1; }
.status { display: inline-block; margin-top: .75rem; font-weight: 700; }
.online { color: #26733a; }
.offline { color: #a13a2a; }
section { margin: 1rem 0; padding: 1.25rem; border: 1px solid #d5cdbc; border-radius: .75rem; background: #fffdf8; }
h2 { margin-top: 0; font-size: 1.1rem; }
code { display: block; overflow-wrap: anywhere; padding: .75rem; border-radius: .4rem; background: #ece5d7; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr)); gap: 1rem; margin: 0; }
.grid div { min-width: 0; }
dt { color: #5c6758; font-size: .9rem; }
dd { margin: .2rem 0 0; font-size: 1.35rem; font-weight: 700; overflow-wrap: anywhere; }
a { color: #245c96; }
[hidden] { display: none !important; }
form { display: grid; gap: .8rem; margin-top: 1rem; }
label { display: grid; gap: .3rem; font-weight: 700; }
input, textarea, select, button { font: inherit; }
input, textarea, select { width: 100%; padding: .65rem; border: 1px solid #a9a18f; border-radius: .4rem; background: transparent; color: inherit; }
textarea { min-height: 5rem; resize: vertical; }
.check { display: flex; align-items: center; gap: .5rem; }
.check input { width: auto; }
button { width: fit-content; padding: .65rem 1rem; border: 0; border-radius: .4rem; background: #245c96; color: white; font-weight: 700; cursor: pointer; }
button:disabled { opacity: .55; cursor: wait; }
.signer { padding: .8rem; border: 1px solid #d5cdbc; border-radius: .5rem; }
.signer-actions { display: flex; flex-wrap: wrap; gap: .6rem; align-items: center; }
details { margin-top: .8rem; }
summary { cursor: pointer; font-weight: 700; }
.warning { color: #8b3a2b; font-size: .9rem; }
.message { min-height: 1.5em; }
footer { margin-top: 2rem; color: #5c6758; font-size: .9rem; }
@media (prefers-color-scheme: dark) {
  body { background: #171a17; color: #edf1ea; }
  section { border-color: #3b4439; background: #20251f; }
  code { background: #30372e; }
  .eyebrow, dt, footer { color: #b9c4b5; }
  .online { color: #79d88d; }
  .offline { color: #ff9a86; }
  a { color: #91c5ff; }
}
"#;

fn escape_html(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len());
    for c in value.chars() {
        match c {
            '&' => escaped.push_str("&amp;"),
            '<' => escaped.push_str("&lt;"),
            '>' => escaped.push_str("&gt;"),
            '"' => escaped.push_str("&quot;"),
            '\'' => escaped.push_str("&#39;"),
            _ => escaped.push(c),
        }
    }
    escaped
}

fn relay_url(host: &str) -> Option<String> {
    host.parse::<Authority>()
        .ok()
        .map(|authority| format!("ws://{}:7777", authority.host()))
}

fn render_home(status: &Value, profile: &profile::Profile, relay: &str) -> String {
    let connected = status["fips"]["connected"].as_bool().unwrap_or(false);
    let connection = if connected {
        "Connected"
    } else {
        "Disconnected"
    };
    let connection_class = if connected { "online" } else { "offline" };
    let npub = escape_html(status["fips"]["npub"].as_str().unwrap_or("Starting…"));
    let name = escape_html(&profile.metadata.name);
    let about = profile
        .metadata
        .about
        .as_deref()
        .map(escape_html)
        .map(|about| format!("<p>{about}</p>"))
        .unwrap_or_default();
    let relay = escape_html(relay);
    let version = escape_html(status["version"].as_str().unwrap_or("unknown"));
    let befriend = escape_html(status["config"]["befriend"].as_str().unwrap_or("unknown"));
    let sync_policy = match status["config"]["sync"].as_bool() {
        Some(true) => "Every recognized Totem",
        Some(false) => "Friends only",
        None => "Unknown",
    };
    let mesh = status["fips"]["mesh_size"].as_u64().unwrap_or(0);
    let peers = status["peers"].as_u64().unwrap_or(0);
    let recognized = status["recognized"].as_u64().unwrap_or(0);
    let syncs = status["events"]["totem.sync.done"].as_u64().unwrap_or(0);

    format!(
        r#"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} · Totem</title>
<style>{STYLE}</style>
<script src="/nsec-signer.js" defer></script>
<script src="/app.js" defer></script>
</head>
<body>
<main>
<header>
<p class="eyebrow">Carry the network</p>
<h1 id="device-name">{name}</h1>
<span class="status {connection_class}"><span aria-hidden="true">●</span> {connection}</span>
{about}
</header>
<section aria-labelledby="relay-heading">
<h2 id="relay-heading">Local relay</h2>
<p>Point any Nostr client at:</p>
<code>{relay}</code>
</section>
<section aria-labelledby="identity-heading">
<h2 id="identity-heading">Device identity</h2>
<code>{npub}</code>
</section>
<section aria-labelledby="status-heading">
<h2 id="status-heading">Status</h2>
<dl class="grid">
<div><dt>Mesh nodes</dt><dd>{mesh}</dd></div>
<div><dt>Direct peers</dt><dd>{peers}</dd></div>
<div><dt>Recognized Totems</dt><dd>{recognized}</dd></div>
<div><dt>Completed syncs</dt><dd>{syncs}</dd></div>
</dl>
</section>
<section aria-labelledby="policy-heading">
<h2 id="policy-heading">Policy</h2>
<dl class="grid">
<div><dt>Sync</dt><dd>{sync_policy}</dd></div>
<div><dt>Friendship</dt><dd>{befriend}</dd></div>
</dl>
</section>
<section id="owner-controls" aria-labelledby="owner-heading">
<h2 id="owner-heading">Owner controls</h2>
<p id="owner-state">Loading claim state…</p>
<div class="signer" aria-labelledby="signer-heading">
<h3 id="signer-heading">Signer</h3>
<p id="signer-state">Looking for a NIP-07 extension…</p>
<div class="signer-actions">
<button id="use-extension" type="button">Use browser extension</button>
<button id="signer-logout" type="button" hidden>Forget signer</button>
</div>
<details>
<summary>Development escape hatch: use nsec</summary>
<p class="warning">The nsec stays in this page's memory and is cleared on logout or navigation. Use a development key only.</p>
<form id="nsec-form">
<label>nsec <input id="nsec" type="password" autocomplete="new-password" spellcheck="false" required></label>
<button type="submit">Use nsec locally</button>
</form>
</details>
</div>
<button id="claim" type="button" hidden>Claim this Totem</button>
<div id="settings" hidden>
<form id="metadata-form">
<h3>Public profile</h3>
<label>Name <input id="metadata-name" maxlength="64" required></label>
<label>Display name <input id="metadata-display-name" maxlength="128"></label>
<label>About <textarea id="metadata-about" maxlength="1024"></textarea></label>
<label>Picture URL <input id="metadata-picture" type="url" maxlength="2048"></label>
<label>Website <input id="metadata-website" type="url" maxlength="2048"></label>
<button type="submit">Publish profile</button>
</form>
<form id="config-form">
<h3>Engagement policy</h3>
<label class="check"><input id="config-sync" type="checkbox"> Sync every recognized Totem</label>
<label>Friendship
<select id="config-befriend">
<option value="ask">Ask</option>
<option value="auto">Automatic</option>
<option value="never">Never</option>
</select>
</label>
<button type="submit">Save policy</button>
</form>
</div>
<p id="owner-message" class="message" role="status" aria-live="polite"></p>
<noscript>Owner controls require JavaScript and a NIP-07 or nsec signer.</noscript>
</section>
<p><a href="/">Refresh status</a></p>
<footer>totemd {version}</footer>
</main>
</body>
</html>"#
    )
}

const APP_JS: &str = include_str!("../web/app.js");
const NSEC_SIGNER_JS: &str = include_str!("../web/nsec-signer.js");

fn javascript(source: &'static str) -> Response {
    (
        [
            (header::CACHE_CONTROL, "no-store"),
            (header::CONTENT_TYPE, "text/javascript; charset=utf-8"),
            (header::X_CONTENT_TYPE_OPTIONS, "nosniff"),
        ],
        source,
    )
        .into_response()
}

async fn app_js() -> Response {
    javascript(APP_JS)
}

async fn nsec_signer_js() -> Response {
    javascript(NSEC_SIGNER_JS)
}

async fn root(State(control): State<ControlState>, headers: HeaderMap) -> Response {
    let host = headers
        .get(header::HOST)
        .and_then(|value| value.to_str().ok())
        .and_then(relay_url)
        .unwrap_or_else(|| "ws://this-totem:7777".into());
    let status = bus::handle(json!({"type": "totem.status.get"}), &control.app);
    let profile = control.profile.read().unwrap().clone();
    (
        [
            (header::CACHE_CONTROL, "no-store"),
            (
                header::CONTENT_SECURITY_POLICY,
                "default-src 'none'; script-src 'self' chrome-extension: moz-extension:; connect-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            ),
            (header::X_CONTENT_TYPE_OPTIONS, "nosniff"),
        ],
        Html(render_home(&status["status"], &profile, &host)),
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
    fn home_page_escapes_dynamic_text() {
        let status = json!({
            "version": "0.1<&\"'",
            "config": {"sync": true, "befriend": "ask<script>"},
            "fips": {"connected": true, "npub": "npub<&\"'", "mesh_size": 3},
            "peers": 2,
            "recognized": 1,
            "events": {"totem.sync.done": 4},
        });
        let profile = profile::Profile {
            metadata: profile::DeviceMetadata {
                name: "name<script>".into(),
                display_name: None,
                about: Some("about<&".into()),
                picture: None,
                website: None,
            },
            source: "kind0",
            nip11_name: "!Totem name".into(),
        };
        let html = render_home(&status, &profile, "ws://totem.invalid:7777/?x=<bad>&y=1");
        assert!(html.starts_with("<!doctype html>"));
        assert!(html.contains("name&lt;script&gt;"));
        assert!(html.contains("about&lt;&amp;"));
        assert!(html.contains("npub&lt;&amp;&quot;&#39;"));
        assert!(html.contains("ask&lt;script&gt;"));
        assert!(html.contains("?x=&lt;bad&gt;&amp;y=1"));
        assert!(html.contains("Every recognized Totem"));
        assert!(html.contains("<script src=\"/nsec-signer.js\" defer></script>"));
        assert!(!html.contains("name<script>"));
    }
}
