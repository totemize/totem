//! The two binds (`10-control-plane.md`): the public web port (guest page /
//! owner app / challenge endpoint — all later) and the loopback-only bus.
//! Ports are TBD in `07-conventions.md`; env-overridable until pinned.

use std::{convert::Infallible, net::SocketAddr, sync::Arc};

use axum::{
    extract::State,
    response::sse::{Event, KeepAlive, Sse},
    routing::{get, post},
    Json, Router,
};
use serde_json::{json, Value};
use tokio_stream::{wrappers::BroadcastStream, StreamExt};

use crate::{bus, state::AppState};

fn addr_from_env(var: &str, default: &str) -> SocketAddr {
    std::env::var(var)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or_else(|| default.parse().expect("default addr"))
}

pub async fn serve() {
    let st = Arc::new(AppState::new());

    // Loopback only: the bus is kernel-internal by construction.
    let bus_router = Router::new()
        .route("/bus", post(bus_post))
        .route("/bus/events", get(bus_events))
        .with_state(st.clone());
    // Public: becomes the guest page + owner app + /totem/challenge.
    let web_router = Router::new()
        .route("/", get(root))
        .with_state(st.clone());

    let web_addr = addr_from_env("TOTEMD_WEB_ADDR", "0.0.0.0:8080");
    let bus_addr = addr_from_env("TOTEMD_BUS_ADDR", "127.0.0.1:8081");
    let web_l = tokio::net::TcpListener::bind(web_addr).await.expect("web bind");
    let bus_l = tokio::net::TcpListener::bind(bus_addr).await.expect("bus bind");

    tracing::info!(
        version = env!("CARGO_PKG_VERSION"),
        web = %web_addr,
        bus = %bus_addr,
        "totemd starting (bus loopback only)"
    );

    let web = tokio::spawn(async move {
        axum::serve(web_l, web_router)
            .with_graceful_shutdown(async {
                let _ = tokio::signal::ctrl_c().await;
            })
            .await
    });
    let bus = tokio::spawn(async move {
        axum::serve(bus_l, bus_router)
            .with_graceful_shutdown(async {
                let _ = tokio::signal::ctrl_c().await;
            })
            .await
    });
    let _ = tokio::join!(web, bus);
    tracing::info!("totemd shut down");
}

async fn root(State(_st): State<Arc<AppState>>) -> Json<Value> {
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
