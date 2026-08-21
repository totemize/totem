//! totemd — Totem control-plane daemon and net code.
//! Spec: spec/10-control-plane.md
//!
//! One binary, two faces: `totemd serve` (daemon) and `totemctl` (client
//! mode, selected by argv[0] or the first argument). Client mode talks to
//! the daemon's loopback bus; it introduces no separate API.

use std::io::IsTerminal;

mod auth;
mod bus;
mod challenge;
mod cli;
mod config;
mod encounter;
mod fips;
mod http;
mod owner;
mod probe;
mod profile;
mod relay;
mod state;
mod sync;
mod web;

const HELP: &str = "totemd — Totem control plane

Usage:
  totemd serve
  totemd totemctl <command>
  totemctl <command>

Run `totemctl help` for client commands.";

fn main() {
    let mut args = std::env::args();
    let argv0 = args.next().unwrap_or_default();
    let mode = if argv0.ends_with("totemctl") {
        "totemctl".to_string()
    } else {
        match args.next() {
            Some(m) => m,
            None => {
                eprintln!("{HELP}");
                std::process::exit(2);
            }
        }
    };
    let rest: Vec<String> = args.collect();

    match mode.as_str() {
        "serve" => {
            tracing_subscriber::fmt()
                .with_ansi(std::io::stdout().is_terminal())
                .with_env_filter(
                    tracing_subscriber::EnvFilter::from_default_env()
                        .add_directive("info".parse().expect("directive")),
                )
                .init();
            let rt = tokio::runtime::Runtime::new().expect("tokio runtime");
            rt.block_on(web::serve());
        }
        "totemctl" => cli::run(&rest),
        "help" | "-h" | "--help" => println!("{HELP}"),
        "version" | "-V" | "--version" => println!("totemd {}", env!("CARGO_PKG_VERSION")),
        other => {
            eprintln!("totemd: unknown mode '{other}' (run `totemd --help`)");
            std::process::exit(2);
        }
    }
}
