//! Small bounded HTTP helpers shared by NIP-11 and challenge probes.

use std::io::Read;

use serde_json::Value;

const FETCH_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(5);
const MAX_JSON_BYTES: u64 = 64 * 1024;

pub fn url(ip: &str, port: u16, path: &str) -> Option<String> {
    if ip.is_empty() {
        return None;
    }
    let host = if ip.contains(':') {
        format!("[{ip}]")
    } else {
        ip.to_string()
    };
    Some(format!("http://{host}:{port}{path}"))
}

pub fn get_json(url: &str, accept: Option<&str>) -> Result<Value, String> {
    let agent = ureq::AgentBuilder::new().timeout(FETCH_TIMEOUT).build();
    let mut request = agent.get(url);
    if let Some(value) = accept {
        request = request.set("Accept", value);
    }
    let response = request.call().map_err(|e| format!("GET {url}: {e}"))?;
    let mut body = String::new();
    response
        .into_reader()
        .take(MAX_JSON_BYTES + 1)
        .read_to_string(&mut body)
        .map_err(|e| format!("body: {e}"))?;
    if body.len() as u64 > MAX_JSON_BYTES {
        return Err(format!("body exceeds {MAX_JSON_BYTES} bytes"));
    }
    serde_json::from_str(&body).map_err(|e| format!("body: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_ipv4_and_ipv6_urls() {
        assert_eq!(url("127.0.0.1", 80, "/x").unwrap(), "http://127.0.0.1:80/x");
        assert_eq!(url("fd00::1", 80, "/x").unwrap(), "http://[fd00::1]:80/x");
        assert!(url("", 80, "/x").is_none());
    }
}
