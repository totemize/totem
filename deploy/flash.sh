#!/usr/bin/env bash
# Build totemd for the bench fleet's arches and install it like fips/strfry:
# /usr/local/bin + systemd unit. Also installs the unprivileged strfry sync
# runner and DB group access. Usage: deploy/flash.sh [device ...]
# (default: totem metot motown; unreachable devices are skipped)
set -euo pipefail
cd "$(dirname "$0")/.."
command -v clang >/dev/null || { echo "clang is required for static nostr/secp256k1 cross builds" >&2; exit 1; }

declare -A ARCH=(
  [totem]=arm-unknown-linux-musleabihf
  [metot]=arm-unknown-linux-musleabihf
  [motown]=aarch64-unknown-linux-musl
)

devs=("$@")
[ $# -eq 0 ] && devs=(totem metot motown)

for d in "${devs[@]}"; do
  t=${ARCH[$d]:-}
  [ -z "$t" ] && { echo "== $d: unknown device, skip"; continue; }
  echo "== $d ($t)"
  ssh -o ConnectTimeout=8 "$d" true 2>/dev/null || { echo "   unreachable, skip"; continue; }
  (cd totemd && cargo build --release --quiet --target "$t")
  scp -q "totemd/target/$t/release/totemd" "$d:/tmp/totemd.new"
  scp -q deploy/totemd.toml "$d:/tmp/totemd.toml"
  scp -q deploy/totem-strfry deploy/systemd/strfry-sync.conf "$d:/tmp/"
  ssh "$d" 'sudo install -m755 /tmp/totemd.new /usr/local/bin/totemd && sudo ln -sf /usr/local/bin/totemd /usr/local/bin/totemctl && sudo install -d -m755 /etc/totemd /usr/local/libexec /etc/systemd/system/strfry.service.d && { test -e /etc/totemd/config.toml || sudo install -m644 /tmp/totemd.toml /etc/totemd/config.toml; } && sudo install -m755 /tmp/totem-strfry /usr/local/libexec/totem-strfry && sudo install -m644 /tmp/strfry-sync.conf /etc/systemd/system/strfry.service.d/totemd-sync.conf && sudo usermod -aG strfry totem && sudo chgrp strfry /etc/strfry.conf /var/lib/strfry && sudo chmod 640 /etc/strfry.conf && sudo chmod 2770 /var/lib/strfry && sudo find /var/lib/strfry -maxdepth 1 -type f -exec chgrp strfry {} + -exec chmod 660 {} +'
  ssh "$d" 'cat > /tmp/totemd.service && sudo install -m644 /tmp/totemd.service /etc/systemd/system/totemd.service && sudo systemctl daemon-reload && sudo systemctl enable totemd && sudo systemctl restart totemd' < deploy/systemd/totemd.service
  sleep 2
  ssh "$d" 'systemctl is-active totemd; totemctl status'
done
