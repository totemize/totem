//! `totemctl` — client mode: a plain HTTP client of the loopback bus.
//! Same binary, no separate API (`10-control-plane.md`).

use serde_json::{json, Value};

fn bus_url() -> String {
    let addr = std::env::var("TOTEMD_BUS_ADDR").unwrap_or_else(|_| "127.0.0.1:8081".into());
    format!("http://{addr}/bus")
}

fn events_url() -> String {
    bus_url().replace("/bus", "/bus/events")
}

fn post(msg: Value) -> Value {
    match ureq::post(&bus_url()).send_json(msg) {
        Ok(resp) => resp.into_json().expect("bus returned invalid JSON"),
        Err(e) => {
            eprintln!("totemctl: bus unreachable ({e}) — is totemd running?");
            std::process::exit(1);
        }
    }
}

fn show(v: Value) {
    println!("{}", serde_json::to_string_pretty(&v).expect("json"));
}

pub fn run(args: &[String]) {
    match args.first().map(String::as_str) {
        Some("status") => show(post(json!({"type": "totem.status.get", "id": "1"}))),
        Some("config") => show(post(json!({"type": "totem.config.get", "id": "1"}))),
        Some("peers") => show(post(json!({"type": "totem.peers.get", "id": "1"}))),
        // `totemctl call <type> [json payload]` — escape hatch for any
        // registered (or future) message.
        Some("call") => {
            let typ = args
                .get(1)
                .map(String::as_str)
                .map(str::to_string)
                .unwrap_or_else(|| {
                    eprintln!("usage: totemctl call <type> [json payload]");
                    std::process::exit(2);
                });
            let payload: Value = match args.get(2) {
                Some(p) => serde_json::from_str(p).unwrap_or_else(|e| {
                    eprintln!("totemctl: invalid JSON payload: {e}");
                    std::process::exit(2);
                }),
                None => json!({}),
            };
            // Merge `type` into the payload object.
            let mut msg = payload;
            if !msg.is_object() {
                eprintln!("totemctl: payload must be a JSON object");
                std::process::exit(2);
            }
            msg["type"] = json!(typ);
            show(post(msg))
        }
        // Attach to the SSE push stream; skips keep-alive comment lines.
        Some("events") => {
            let resp = match ureq::get(&events_url()).call() {
                Ok(r) => r,
                Err(e) => {
                    eprintln!("totemctl: bus unreachable ({e}) — is totemd running?");
                    std::process::exit(1);
                }
            };
            use std::io::{BufRead, BufReader};
            for line in BufReader::new(resp.into_reader()).lines() {
                let line = line.expect("stream read");
                if !line.is_empty() && !line.starts_with(':') {
                    println!("{line}");
                }
            }
        }
        other => {
            eprintln!(
                "usage: totemctl status | config | peers | events | call <type> [json payload]\nunknown command: {}",
                other.unwrap_or("(none)")
            );
            std::process::exit(2);
        }
    }
}
