# Metot state-caption proof

This directory records the deterministic and physical checks for Python release
`sha256-ae10b450ccc3fa94f7208ed1bb7c1482cc7c73a73e39447e171e4cee73a96a33`,
deployed only to the authorized Waveshare V4 display host, metot.

- `metot-caption-proof-atlas.png` is the 229-frame, mode-1 atlas generated on
  metot by `totem-screen proof-captions`. It covers all 130 complete captions,
  representative progressive prefixes for every scene, and every existing face
  sequence without submitting a long physical replay.
- `metot-caption-reveal-camera.mp4` is the complete controlled service-restart
  capture. The admitted charging caption was `drinking organized lightning.`
- `metot-caption-reveal-contact-sheet.png` isolates the three stable prefix
  states: `drinking`, `drinking organized`, and the complete caption. Existing
  words keep one fixed origin; the character, header, footer rule, `[•]` friend
  badge, paper-note glyph, and live `404` note count do not move.

The first runtime prefix completed at 02:12:19.128 after the safe full refresh.
The second and third completed at 02:12:22.120 and 02:12:23.405. This gives the
initial prefix a readable post-transfer hold and then advances partial-refresh
prefixes about 1.29 seconds apart. The panel stayed crisp and showed no periodic
full-refresh flash; metot had `TOTEM_EINK_FULL_REFRESH_EVERY=0`. The caption is
small, bold, centered from its final width, and visibly separated from the
footer. `totemd`, `totem.service`, and `totem-screen.service` were active after
the check. A second metot-only convergence reused the exact release and finished
`ok=100 changed=0 failed=0 unreachable=0`.

## SHA-256

```text
2bb280941e3e0e0dcf1b1bf8a8f59e4ec424d496ec5e58f6891166f440b869cb  metot-caption-proof-atlas.png
6dc4368c13359b1c3f15e5b0842c4d35eabcc0becce04afa2abd23526e737093  metot-caption-reveal-camera.mp4
5202572e3fd10b90f47fc3a4f1c45f71d9fa984621ce8803676570cdfb3d5fc0  metot-caption-reveal-contact-sheet.png
```
