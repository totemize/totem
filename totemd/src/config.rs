//! `/etc/totemd/config.toml` — operator *intent*, never mechanism.
//!
//! Missing file → defaults. Present but invalid → fail fast at startup
//! (a daemon silently running the wrong policy is worse than no daemon).
//! Auto-connect/rendezvous is fips's config (`/etc/fips/fips.yaml`), not
//! ours — these keys govern the engagement ladder only (`10-control-plane.md`).

use std::path::Path;

#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Befriend {
    Auto,
    Ask,
    Never,
}

#[derive(Clone, Debug, PartialEq, serde::Serialize)]
pub struct Config {
    pub probe: bool,
    pub verdict_ttl_hours: u64,
    pub befriend: Befriend,
    pub sync: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            probe: true,
            verdict_ttl_hours: 24,
            befriend: Befriend::Ask,
            sync: true,
        }
    }
}

#[derive(serde::Deserialize, Default)]
#[serde(deny_unknown_fields)]
struct Raw {
    #[serde(default)]
    net: Net,
    #[serde(default)]
    policy: Policy,
}

#[derive(serde::Deserialize, Default)]
#[serde(deny_unknown_fields)]
struct Net {
    probe: Option<bool>,
    verdict_ttl_hours: Option<u64>,
}

#[derive(serde::Deserialize, Default)]
#[serde(deny_unknown_fields)]
struct Policy {
    befriend: Option<String>,
    sync: Option<bool>,
}

impl Config {
    /// Parse from a TOML string; keys are strict so typos cannot silently
    /// enable an operator-disabled policy.
    pub fn parse(s: &str) -> Result<Self, String> {
        let raw: Raw = toml::from_str(s).map_err(|e| format!("parse config: {e}"))?;
        let mut c = Config::default();
        if let Some(v) = raw.net.probe {
            c.probe = v;
        }
        if let Some(v) = raw.net.verdict_ttl_hours {
            c.verdict_ttl_hours = v;
        }
        if let Some(v) = raw.policy.sync {
            c.sync = v;
        }
        if let Some(v) = &raw.policy.befriend {
            c.befriend = match v.as_str() {
                "auto" => Befriend::Auto,
                "ask" => Befriend::Ask,
                "never" => Befriend::Never,
                other => return Err(format!("policy.befriend: '{other}' (want auto|ask|never)")),
            };
        }
        Ok(c)
    }

    /// Load from disk: missing file → defaults, anything else → error.
    pub fn load(path: &Path) -> Result<Self, String> {
        match std::fs::read_to_string(path) {
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(Self::default()),
            Err(e) => Err(format!("read {}: {e}", path.display())),
            Ok(s) => Self::parse(&s),
        }
    }

    pub fn path() -> std::path::PathBuf {
        std::env::var("TOTEMD_CONFIG")
            .map(Into::into)
            .unwrap_or_else(|_| "/etc/totemd/config.toml".into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_file_is_defaults() {
        let c = Config::load(std::path::Path::new("/nonexistent/totemd.toml")).unwrap();
        assert_eq!(c, Config::default());
        assert_eq!(c.befriend, Befriend::Ask);
        assert!(c.probe && c.sync);
    }

    #[test]
    fn parses_all_keys() {
        let c = Config::parse(
            "[net]\nprobe = false\nverdict_ttl_hours = 8\n\
             [policy]\nbefriend = \"auto\"\nsync = false\n",
        )
        .unwrap();
        assert!(!c.probe && !c.sync);
        assert_eq!(c.verdict_ttl_hours, 8);
        assert_eq!(c.befriend, Befriend::Auto);
    }

    #[test]
    fn partial_file_keeps_other_defaults() {
        let c = Config::parse("[policy]\nbefriend = \"never\"\n").unwrap();
        assert_eq!(c.befriend, Befriend::Never);
        assert_eq!(c.verdict_ttl_hours, 24);
    }

    #[test]
    fn bad_value_unknown_key_or_bad_toml_fails_fast() {
        assert!(Config::parse("[policy]\nbefriend = \"sometimes\"\n").is_err());
        assert!(Config::parse("[net]\nproeb = false\n").is_err());
        assert!(Config::parse("[net\nbroken\n").is_err());
    }
}
