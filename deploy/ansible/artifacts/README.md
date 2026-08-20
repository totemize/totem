# Deployment artifacts

Architecture-specific binaries are intentionally not committed. Create them
with `../scripts/stage-artifacts.sh`; the result is:

```text
artifacts/<architecture>/
├── fips/{fips,fipsctl,fipstop}
├── strfry-rootfs.tar.gz
└── SHA256SUMS
```

FIPS is built from its locked Rust checkout. The strfry input is a previously
built runtime root containing `bin/strfry`, its musl loader, and libraries.
Ansible hashes every artifact, copies only changed content, and records the
installed strfry checksum as a device sentinel.

The current bench FIPS baseline is revision
`23ec0a7b811a0e986fe2d2cb51fffe8f10f7a57d`. The armv6 strfry lineage and
alignment patches are documented in the journey journal; motown instead runs
protocol-0-compatible strfry master `5d89a62`. Its FIPS target is
`aarch64-unknown-linux-musl` and its strfry runtime is aarch64 Alpine/musl; do
not reuse the armv6 archive.

The deployment verifier is authoritative for relay capability: every staged
strfry artifact must return `negentropy: 1` and advertise NIP `77`. A live
2026-08-20 audit caught an incompatible motown artifact; it was replaced with
protocol-0 master rather than weakening the verifier.
