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

## Optional radio lanes

When the device-manager extension from PR #22 is present, the operator API can
request LE L2CAP CoC and Wi-Fi Aware mechanisms without moving Myco payloads
through the device manager:

- `totem-myco transports` reports the live, reasoned device-manager capability
  document and the lanes requested by this service.
- `totem-myco coc-connect <npub> <address> <psm>` asks the device manager to
  establish a CoC and hand its file descriptor directly to FIPS.
- `totem-myco aware-discover [udp-port] [seconds]` publishes
  `myco.fips.v1`; its service data contains only the two-byte little-endian UDP
  port, never an identity.
- `totem-myco aware-connect <npub> <match-id> [udp-port]` asks the device
  manager for the data path, converts the scoped IPv6 address to a numeric
  scope, and submits it to the existing FIPS control socket as a UDP peer.
- `totem-myco route <npub> <lan|softap> <udp-endpoint>` submits an already
  discovered LAN or SoftAP UDP endpoint through the same FIPS control seam.

All of the native integration's HTTP/WebSocket/blob traffic continues to use
the peer's stable FIPS address on `fips0`. CoC, Aware, LAN, and SoftAP are lanes
under that overlay, so Noise identity, routing, and fallback remain FIPS-owned.
The Myco service calls only loopback device-manager HTTP and the existing
group-scoped `/run/fips/control.sock`; it gains no radio or key privilege.

Production Wi-Fi Aware data-path creation is currently reported unsupported by
the Linux device manager until an NDP backend exists. End-to-end CoC likewise
requires the FIPS-side descriptor receiver. These commands return the typed
upstream failure and leave the existing FIPS-TUN path available.
