//! The two binds (`10-control-plane.md`): the public web port (guest page /
//! owner app / challenge endpoint) and the loopback-only bus. Ports are
//! pinned in `07-conventions.md`; bind addresses remain env-overridable.

use std::{convert::Infallible, net::SocketAddr, sync::Arc};

use axum::{
    extract::State,
    http::{header, uri::Authority, HeaderMap},
    response::{
        sse::{Event, KeepAlive, Sse},
        Html, IntoResponse, Response,
    },
    routing::{get, post},
    Json, Router,
};
use serde_json::{json, Value};
use tokio_stream::{wrappers::BroadcastStream, StreamExt};

use crate::{bus, challenge, config, fips, state::AppState, sync};

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
    tracing::info!(
        probe = cfg.probe,
        befriend = ?cfg.befriend,
        sync = cfg.sync,
        verdict_ttl_hours = cfg.verdict_ttl_hours,
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
    let st = Arc::new(AppState::new(cfg));

    // Loopback only: the bus is kernel-internal by construction.
    let bus_router = Router::new()
        .route("/bus", post(bus_post))
        .route("/bus/events", get(bus_events))
        .with_state(st.clone());
    // Public: guest page + the signed challenge responder.
    let web_router = Router::new()
        .route("/", get(root))
        .with_state(st.clone())
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

    tracing::info!(
        version = env!("CARGO_PKG_VERSION"),
        web = %web_addr,
        bus = %bus_addr,
        "totemd starting (bus loopback only)"
    );

    let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(false);
    let shutdown_st = st.clone();
    let fips_abort = fips_task.abort_handle();
    tokio::spawn(async move {
        shutdown_signal().await;
        fips_abort.abort();
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

fn render_home(status: &Value, relay: &str) -> String {
    let connected = status["fips"]["connected"].as_bool().unwrap_or(false);
    let connection = if connected {
        "Connected"
    } else {
        "Disconnected"
    };
    let connection_class = if connected { "online" } else { "offline" };
    let npub = escape_html(status["fips"]["npub"].as_str().unwrap_or("Starting…"));
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
<title>Totem</title>
<style>{STYLE}</style>
</head>
<body>
<main>
<header>
<p class="eyebrow">Carry the network</p>
<h1>Totem</h1>
<span class="status {connection_class}"><span aria-hidden="true">●</span> {connection}</span>
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
<p><a href="/">Refresh status</a></p>
<footer>totemd {version} · Read-only status</footer>
</main>
</body>
</html>"#
    )
}

async fn root(State(st): State<Arc<AppState>>, headers: HeaderMap) -> Response {
    let host = headers
        .get(header::HOST)
        .and_then(|value| value.to_str().ok())
        .and_then(relay_url)
        .unwrap_or_else(|| "ws://this-totem:7777".into());
    let status = bus::handle(json!({"type": "totem.status.get"}), &st);
    (
        [
            (header::CACHE_CONTROL, "no-store"),
            (
                header::CONTENT_SECURITY_POLICY,
                "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            ),
            (header::X_CONTENT_TYPE_OPTIONS, "nosniff"),
        ],
        Html(render_home(&status["status"], &host)),
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
        let html = render_home(&status, "ws://totem.invalid:7777/?x=<bad>&y=1");
        assert!(html.starts_with("<!doctype html>"));
        assert!(html.contains("npub&lt;&amp;&quot;&#39;"));
        assert!(html.contains("ask&lt;script&gt;"));
        assert!(html.contains("?x=&lt;bad&gt;&amp;y=1"));
        assert!(html.contains("Every recognized Totem"));
        assert!(!html.contains("<script>"));
    }
}
