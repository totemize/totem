//! Device-signed kind-0 profile and the derived strfry NIP-11 name.

use std::{
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::OpenOptionsExt,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::Mutex,
};

use nostr::{
    event::IntoEventBuilder,
    nips::nip01::Metadata,
    prelude::{Event, Kind, PublicKey, Timestamp, Url},
};

use crate::{challenge::Signer, config::Config};

const RUNNER: &str = "/usr/local/libexec/totem-strfry";
const NAME_PATH: &str = "/var/lib/totemd/nip11-name";
const PREFIX: &str = "!Totem";
const MAX_NIP11_CHARS: usize = 29;
static WRITE_LOCK: Mutex<()> = Mutex::new(());

#[derive(Clone, Debug, PartialEq, serde::Deserialize, serde::Serialize)]
#[serde(deny_unknown_fields)]
pub struct DeviceMetadata {
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub display_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub about: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub picture: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub website: Option<String>,
}

#[derive(Clone, Debug, serde::Serialize)]
pub struct Profile {
    #[serde(flatten)]
    pub metadata: DeviceMetadata,
    pub source: &'static str,
    pub nip11_name: String,
}

pub fn reconcile(config: &Config, public_key: PublicKey) -> Profile {
    let runner = runner_path();
    let path = name_path();
    let profile = match profile_from_relay(config, public_key, &runner) {
        Ok(profile) => profile,
        Err(error) => {
            tracing::warn!(%error, "could not read device metadata; using configured name");
            fallback(config)
        }
    };
    reconcile_name(&path, &profile);
    profile
}

pub fn publish(signer: &Signer, metadata: DeviceMetadata) -> Result<(Profile, Event), String> {
    publish_with(signer, metadata, &runner_path(), &name_path())
}

fn publish_with(
    signer: &Signer,
    metadata: DeviceMetadata,
    runner: &Path,
    name_path: &Path,
) -> Result<(Profile, Event), String> {
    let metadata = validate(metadata)?;
    let _writer = WRITE_LOCK.lock().unwrap();
    let latest = latest_own_event(runner, signer.public_key())?;
    let latest_timestamp = latest
        .as_ref()
        .map(|event| event.created_at.as_secs())
        .unwrap_or(0);
    let created_at = Timestamp::from_secs(
        Timestamp::now()
            .as_secs()
            .max(latest_timestamp.saturating_add(1)),
    );
    let nostr_metadata = Metadata {
        name: Some(metadata.name.clone()),
        display_name: metadata.display_name.clone(),
        about: metadata.about.clone(),
        website: metadata.website.clone(),
        picture: metadata.picture.clone(),
        ..Metadata::new()
    };
    let event = signer.finalize(nostr_metadata.into_event_builder(), created_at)?;
    import_event(runner, &event)?;
    let stored = scan_event(
        runner,
        serde_json::json!({ "ids": [event.id.to_hex()], "limit": 1 }),
    )?
    .ok_or_else(|| "strfry import did not store metadata event".to_string())?;
    stored
        .verify()
        .map_err(|e| format!("stored metadata signature: {e}"))?;
    if stored.id != event.id {
        return Err("strfry metadata verification returned another event".into());
    }
    let profile = Profile {
        nip11_name: nip11_name(&metadata.name),
        metadata,
        source: "kind0",
    };
    reconcile_name(name_path, &profile);
    Ok((profile, event))
}

fn profile_from_relay(
    config: &Config,
    public_key: PublicKey,
    runner: &Path,
) -> Result<Profile, String> {
    let Some(event) = latest_own_event(runner, public_key)? else {
        return Ok(fallback(config));
    };
    let metadata: Metadata =
        serde_json::from_str(&event.content).map_err(|e| format!("kind 0 metadata: {e}"))?;
    let name = metadata
        .name
        .and_then(usable_name)
        .unwrap_or_else(|| config.device_name.clone());
    Ok(Profile {
        nip11_name: nip11_name(&name),
        metadata: DeviceMetadata {
            name,
            display_name: metadata.display_name.and_then(optional_text),
            about: metadata.about.and_then(optional_text),
            picture: metadata.picture.and_then(optional_text),
            website: metadata.website.and_then(optional_text),
        },
        source: "kind0",
    })
}

fn latest_own_event(runner: &Path, public_key: PublicKey) -> Result<Option<Event>, String> {
    let event = scan_event(
        runner,
        serde_json::json!({
            "kinds": [0],
            "authors": [public_key.to_hex()],
            "limit": 1,
        }),
    )?;
    let Some(event) = event else {
        return Ok(None);
    };
    event
        .verify()
        .map_err(|e| format!("kind 0 signature: {e}"))?;
    if event.pubkey != public_key || event.kind != Kind::Metadata {
        return Err("kind 0 author or kind mismatch".into());
    }
    Ok(Some(event))
}

fn scan_event(runner: &Path, filter: serde_json::Value) -> Result<Option<Event>, String> {
    let output = Command::new(runner)
        .args(["scan", &filter.to_string()])
        .env_clear()
        .stdin(Stdio::null())
        .output()
        .map_err(|e| format!("start {}: {e}", runner.display()))?;
    if !output.status.success() {
        return Err(format!(
            "{} scan {}: {}",
            runner.display(),
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    stdout
        .lines()
        .find(|line| !line.trim().is_empty())
        .map(|line| serde_json::from_str(line).map_err(|e| format!("relay event: {e}")))
        .transpose()
}

fn import_event(runner: &Path, event: &Event) -> Result<(), String> {
    let mut child = Command::new(runner)
        .arg("import")
        .env_clear()
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("start {} import: {e}", runner.display()))?;
    let mut stdin = child.stdin.take().expect("piped stdin");
    stdin
        .write_all(format!("{}\n", event.as_json()).as_bytes())
        .map_err(|e| format!("write strfry import: {e}"))?;
    drop(stdin);
    let output = child
        .wait_with_output()
        .map_err(|e| format!("wait for strfry import: {e}"))?;
    if output.status.success() {
        Ok(())
    } else {
        Err(format!(
            "{} import {}: {}",
            runner.display(),
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        ))
    }
}

pub fn validate(mut metadata: DeviceMetadata) -> Result<DeviceMetadata, String> {
    metadata.name = required_text(metadata.name, 64, "name")?;
    metadata.display_name = bounded_text(metadata.display_name, 128, "display_name")?;
    metadata.about = bounded_multiline(metadata.about, 1024, "about")?;
    metadata.picture = web_url(metadata.picture, "picture")?;
    metadata.website = web_url(metadata.website, "website")?;
    Ok(metadata)
}

fn required_text(value: String, max: usize, field: &str) -> Result<String, String> {
    let value = value.trim();
    if value.is_empty() || value.chars().count() > max || value.chars().any(char::is_control) {
        return Err(format!(
            "{field} must be 1-{max} characters without controls"
        ));
    }
    Ok(value.into())
}

fn bounded_text(value: Option<String>, max: usize, field: &str) -> Result<Option<String>, String> {
    value
        .map(|value| required_text(value, max, field))
        .transpose()
}

fn bounded_multiline(
    value: Option<String>,
    max: usize,
    field: &str,
) -> Result<Option<String>, String> {
    value
        .map(|value| {
            let value = value.trim();
            if value.is_empty()
                || value.chars().count() > max
                || value
                    .chars()
                    .any(|c| c.is_control() && c != '\n' && c != '\t')
            {
                Err(format!(
                    "{field} must be 1-{max} characters without controls"
                ))
            } else {
                Ok(value.into())
            }
        })
        .transpose()
}

fn web_url(value: Option<String>, field: &str) -> Result<Option<String>, String> {
    value
        .map(|value| {
            let value = required_text(value, 2048, field)?;
            let url = Url::parse(&value).map_err(|e| format!("{field}: {e}"))?;
            match url.scheme() {
                "http" | "https" => Ok(value),
                _ => Err(format!("{field} must use http or https")),
            }
        })
        .transpose()
}

fn fallback(config: &Config) -> Profile {
    Profile {
        metadata: DeviceMetadata {
            name: config.device_name.clone(),
            display_name: None,
            about: None,
            picture: None,
            website: None,
        },
        source: "config",
        nip11_name: nip11_name(&config.device_name),
    }
}

fn usable_name(name: String) -> Option<String> {
    let name = name.trim();
    (!name.is_empty() && !name.chars().any(char::is_control)).then(|| name.to_owned())
}

fn optional_text(value: String) -> Option<String> {
    let value = value.trim();
    (!value.is_empty()).then(|| value.to_owned())
}

fn nip11_name(name: &str) -> String {
    let name = name.trim();
    let suffix = if name.eq_ignore_ascii_case("Totem") || name == PREFIX {
        ""
    } else {
        name.strip_prefix("!Totem ").unwrap_or(name)
    };
    if suffix.is_empty() {
        return PREFIX.into();
    }
    let suffix: String = suffix
        .chars()
        .take(MAX_NIP11_CHARS - PREFIX.chars().count() - 1)
        .collect();
    format!("{PREFIX} {suffix}")
}

fn reconcile_name(path: &Path, profile: &Profile) {
    match write_if_changed(path, &profile.nip11_name) {
        Ok(true) => tracing::info!(
            nip11_name = %profile.nip11_name,
            source = profile.source,
            "NIP-11 name reconciled"
        ),
        Ok(false) => tracing::debug!(
            nip11_name = %profile.nip11_name,
            source = profile.source,
            "NIP-11 name unchanged"
        ),
        Err(error) => tracing::warn!(%error, path = %path.display(), "could not write NIP-11 name"),
    }
}

fn runner_path() -> PathBuf {
    std::env::var_os("TOTEMD_STRFRY_RUNNER")
        .map(PathBuf::from)
        .unwrap_or_else(|| RUNNER.into())
}

fn name_path() -> PathBuf {
    std::env::var_os("TOTEMD_NIP11_NAME_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|| NAME_PATH.into())
}

fn write_if_changed(path: &Path, value: &str) -> Result<bool, String> {
    if fs::read(path).ok().as_deref() == Some(value.as_bytes()) {
        return Ok(false);
    }
    let parent = path
        .parent()
        .ok_or_else(|| format!("{} has no parent", path.display()))?;
    fs::create_dir_all(parent).map_err(|e| format!("create {}: {e}", parent.display()))?;
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| format!("invalid name path: {}", path.display()))?;
    let temporary = parent.join(format!(".{file_name}.{}.tmp", std::process::id()));
    let result = (|| {
        let mut file = OpenOptions::new()
            .create(true)
            .truncate(true)
            .write(true)
            .mode(0o644)
            .open(&temporary)
            .map_err(|e| format!("write {}: {e}", temporary.display()))?;
        file.write_all(value.as_bytes())
            .map_err(|e| format!("write {}: {e}", temporary.display()))?;
        file.sync_all()
            .map_err(|e| format!("sync {}: {e}", temporary.display()))?;
        fs::rename(&temporary, path).map_err(|e| format!("replace {}: {e}", path.display()))
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result.map(|()| true)
}

#[cfg(test)]
mod tests {
    use super::*;
    use nostr::{
        event::FinalizeEvent,
        prelude::{EventBuilder, Keys},
    };
    use std::{
        os::unix::fs::PermissionsExt,
        sync::atomic::{AtomicUsize, Ordering},
    };

    static NEXT: AtomicUsize = AtomicUsize::new(0);

    fn temp_dir() -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "totemd-profile-test-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&path).unwrap();
        path
    }

    fn reader(dir: &Path, event: &Event) -> PathBuf {
        let event_path = dir.join("event.json");
        fs::write(&event_path, format!("{}\n", event.as_json())).unwrap();
        let runner = dir.join("reader");
        fs::write(
            &runner,
            format!(
                "#!/bin/sh\nset -eu\n[ \"$1\" = scan ]\n/bin/cat '{}'\n",
                event_path.display()
            ),
        )
        .unwrap();
        executable(&runner);
        runner
    }

    fn writer(dir: &Path, initial: Option<&Event>) -> (PathBuf, PathBuf) {
        let database = dir.join("database.json");
        if let Some(event) = initial {
            fs::write(&database, format!("{}\n", event.as_json())).unwrap();
        }
        let runner = dir.join("writer");
        fs::write(
            &runner,
            format!(
                "#!/bin/sh\nset -eu\ncase \"$1\" in\n  scan) [ ! -f '{0}' ] || /bin/cat '{0}' ;;\n  import) /bin/cat > '{0}' ;;\n  *) exit 2 ;;\nesac\n",
                database.display()
            ),
        )
        .unwrap();
        executable(&runner);
        (runner, database)
    }

    fn executable(path: &Path) {
        let mut permissions = fs::metadata(path).unwrap().permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(path, permissions).unwrap();
    }

    #[test]
    fn signed_kind_zero_overrides_fallback_and_updates_once() {
        let dir = temp_dir();
        let keys = Keys::parse(&format!("{:064x}", 1)).unwrap();
        let event = Metadata::new().name("motown").finalize(&keys).unwrap();
        let runner = reader(&dir, &event);
        let path = dir.join("nip11-name");
        let config = Config {
            device_name: "fallback".into(),
            ..Config::default()
        };

        let profile = profile_from_relay(&config, keys.public_key(), &runner).unwrap();
        reconcile_name(&path, &profile);
        assert_eq!(profile.metadata.name, "motown");
        assert_eq!(fs::read_to_string(&path).unwrap(), "!Totem motown");
        assert!(!write_if_changed(&path, "!Totem motown").unwrap());
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn publish_is_signed_monotonic_and_reconciles_name() {
        let dir = temp_dir();
        let keys = Keys::parse(&format!("{:064x}", 2)).unwrap();
        let old = EventBuilder::new(Kind::Metadata, r#"{"name":"old"}"#)
            .custom_created_at(Timestamp::from_secs(9_999_999_999))
            .finalize(&keys)
            .unwrap();
        let (runner, database) = writer(&dir, Some(&old));
        let path = dir.join("nip11-name");
        let signer = Signer::new(keys);
        let input = DeviceMetadata {
            name: "new name".into(),
            display_name: None,
            about: Some("Carried relay".into()),
            picture: None,
            website: Some("https://example.com".into()),
        };

        let (profile, event) = publish_with(&signer, input, &runner, &path).unwrap();
        event.verify().unwrap();
        assert_eq!(event.created_at.as_secs(), old.created_at.as_secs() + 1);
        assert_eq!(profile.nip11_name, "!Totem new name");
        assert_eq!(fs::read_to_string(path).unwrap(), "!Totem new name");
        let stored: Event =
            serde_json::from_str(fs::read_to_string(database).unwrap().trim()).unwrap();
        assert_eq!(stored.id, event.id);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn invalid_metadata_is_rejected() {
        let metadata = DeviceMetadata {
            name: "".into(),
            display_name: None,
            about: None,
            picture: Some("file:///secret".into()),
            website: None,
        };
        assert!(validate(metadata.clone()).is_err());
        let metadata = DeviceMetadata {
            name: "bad\nname".into(),
            picture: None,
            ..metadata
        };
        assert!(validate(metadata).is_err());
    }

    #[test]
    fn scan_failure_uses_bounded_configured_fallback() {
        let config = Config {
            device_name: "a very long fallback device name".into(),
            ..Config::default()
        };
        let profile = fallback(&config);
        assert_eq!(profile.nip11_name.chars().count(), MAX_NIP11_CHARS);
        assert!(profile.nip11_name.starts_with("!Totem a very long"));
    }
}
