#!/usr/bin/env bash
# Stage architecture-specific FIPS executables and a prebuilt strfry runtime
# for Ansible. Builds remain separate from deployment so a Pi Zero never has
# to compile Rust/C++ during a bare-device install.
set -euo pipefail

usage() {
  echo "usage: $0 <armv6l|aarch64> <fips-source> <strfry-runtime-root>" >&2
  exit 2
}

[[ $# -eq 3 ]] || usage

arch=$1
fips_source=$2
strfry_runtime=$3
script_dir=$(cd "$(dirname "$0")" && pwd)
artifact_root=$(cd "$script_dir/.." && pwd)/artifacts/$arch

case "$arch" in
  armv6l) fips_target=arm-unknown-linux-musleabihf; loader=ld-musl-armhf.so.1 ;;
  aarch64) fips_target=aarch64-unknown-linux-musl; loader=ld-musl-aarch64.so.1 ;;
  *) usage ;;
esac

[[ -f "$fips_source/Cargo.lock" ]] || {
  echo "not a FIPS source checkout: $fips_source" >&2
  exit 1
}
[[ -x "$strfry_runtime/bin/strfry" ]] || {
  echo "missing strfry binary below: $strfry_runtime" >&2
  exit 1
}
[[ -e "$strfry_runtime/lib/$loader" ]] || {
  echo "missing $loader below: $strfry_runtime/lib" >&2
  exit 1
}

if [[ "${TOTEM_SKIP_FIPS_BUILD:-0}" != 1 ]]; then
  rustup target add "$fips_target"
  cargo build --release --locked --target "$fips_target" \
    --manifest-path "$fips_source/Cargo.toml"
fi

mkdir -p "$artifact_root/fips"
for binary in fips fipsctl fipstop; do
  install -m 0755 \
    "$fips_source/target/$fips_target/release/$binary" \
    "$artifact_root/fips/$binary"
done

COPYFILE_DISABLE=1 tar -C "$strfry_runtime" \
  -czf "$artifact_root/strfry-rootfs.tar.gz" .

(
  cd "$artifact_root"
  shasum -a 256 fips/fips fips/fipsctl fips/fipstop \
    strfry-rootfs.tar.gz > SHA256SUMS
)

echo "staged $arch artifacts in $artifact_root"
