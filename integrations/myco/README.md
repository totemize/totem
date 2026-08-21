# Totem Myco integration

`totem-myco` is a Linux/headless host for the pairing and native file-transfer
subset of [Myco](https://github.com/Origami74/myco). It deliberately does not
start another FIPS node. The integration uses the device's existing `fips0` route,
the same Nostr device identity supplied as a systemd credential, and the Myco
wire ports:

- `4873/tcp`: signed pairing events (`POST /pair`)
- `4870/tcp`: Myco `MESH`-wrapped NIP-01 file-control events
- `24243/tcp`: read-only encrypted file blobs
- `127.0.0.1:4874/tcp`: operator API used by the `totem-myco` CLI

The implementation is protocol-compatible with Myco commit
`852bcda8cd0ccc2b604588c9b33c98e2523cea5b` (the paired file-sharing release).
It follows that release's limits: 64 MiB plaintext files, at most 64 tracked
transfers, ten-minute offers, refusal of app/installable payloads, encrypted
Blossom packages, NIP-44 wrapped file keys, and NIP-59 private control messages.

Run `totem-myco help` for operator commands. State and received files live in
`/var/lib/totem-myco` by default. The private device key is never copied into
that directory.

The systemd unit uses `PrivateTmp=true`, so files created in a login shell's
`/tmp` are deliberately invisible to the daemon. Put outbound files somewhere
the service can read, such as `/home/totem`, before running `totem-myco send`.
