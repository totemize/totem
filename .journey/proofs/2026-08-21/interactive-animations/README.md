# Metot interactive-animation proof

This directory records the deterministic physical replay of the exact Python
release deployed to metot:

`sha256-0ca38fc189297b67e0daffa28eadd743c3ef499bc8f3a7f7cc2a92643abc256c`

- `metot-animation-replay-camera.mp4` is the complete 149.982-second Desk View
  capture of all 49 replay frames on the Waveshare 2.13-inch V4 panel.
- `metot-animation-camera-contact-sheet.png` samples the complete camera run.
- `metot-suspicious-camera-contact-sheet.png` captures all seven consecutive
  non-Totem frames. The face stays at one left-side origin and scale while the
  glasses and question mark move.
- `metot-animation-atlas.png` is the exact 1-bit, 250×122 atlas emitted by the
  deployed `totem-screen replay-states` command. It retains metot's configured
  180-degree output rotation.

The executable source in this final release is the source camera-tested below;
the final content hash additionally includes the corrected root deployment
README. Replay completed all 49 catalog frames in order. The command submitted its
first frame as a safe full refresh and the remaining 48 as partial requests;
metot's `TOTEM_EINK_FULL_REFRESH_EVERY=0` prevented scheduled promotion. The
panel remained high contrast with no tofu or clipping. After replay,
`totem.service` and `totem-screen.service` were restored active. The final
metot-only idempotence pass completed `ok=100 changed=0 failed=0 unreachable=0`.

## SHA-256

```text
f23718e275b5c36a48cfe1feaedce3a5ab0bea625bf680d8dadb60a678dc6eb7  metot-animation-atlas.png
2dfa86dba519d6c36f3610769f2715884386dbf94a9b130362e544736e41aa71  metot-animation-camera-contact-sheet.png
025d8b86f1618ff482bbb9ecbd51897b15446ecf7bb33da51110f74e0d071827  metot-animation-replay-camera.mp4
240d54e64e2f8f8f82ab1336bc85a5411e5fd17b2fc56ce151562552c4fe9bc1  metot-suspicious-camera-contact-sheet.png
```
