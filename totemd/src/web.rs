//! The two binds (`10-control-plane.md`): the public web port (guest page /
//! owner app / challenge endpoint) and the loopback-only bus. Ports are
//! pinned in `07-conventions.md`; bind addresses remain env-overridable.

use std::{convert::Infallible, net::SocketAddr, sync::Arc};

use axum::{
    extract::State,
    response::sse::{Event, KeepAlive, Sse},
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

async fn root() -> Json<Value> {
    json!({"app": "totemd", "version": env!("CARGO_PKG_VERSION")}).into()
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
