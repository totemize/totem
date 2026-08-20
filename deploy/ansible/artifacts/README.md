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

The current bench baseline is FIPS revision
`23ec0a7b811a0e986fe2d2cb51fffe8f10f7a57d` and the strfry router lineage at
`5e81e24` (with the armv6 alignment/build patches documented in the journey
journal). Stage artifacts from those pinned sources when reproducing the
deployed armv6 stack.
