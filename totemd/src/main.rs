//! totemd — Totem control-plane daemon and net code.
//! Spec: spec/10-control-plane.md
//!
//! One binary, two faces: `totemd serve` (daemon) and `totemctl` (client
//! mode, selected by argv[0] or the first argument). Client mode talks to
//! the daemon's loopback bus; it introduces no separate API.

fn main() {
    let mut args = std::env::args();
    let argv0 = args.next().unwrap_or_default();
    let mode = if argv0.ends_with("totemctl") {
        "totemctl".to_string()
    } else {
        args.next().unwrap_or_else(|| {
            eprintln!("usage: totemd serve | totemctl <command>");
            std::process::exit(2);
        })
    };

    match mode.as_str() {
        "serve" => {
            eprintln!("totemd: not yet implemented (see spec/10-control-plane.md)");
            std::process::exit(1);
        }
        "totemctl" => {
            eprintln!("totemctl: not yet implemented (bus client)");
            std::process::exit(1);
        }
        other => {
            eprintln!("totemd: unknown mode '{other}' (expected: serve)");
            std::process::exit(2);
        }
    }
}
