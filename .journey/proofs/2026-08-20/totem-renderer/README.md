# Metot renderer proof — 2026-08-20

Target: `metot` (`192.168.8.239`), Waveshare 2.13-inch V4 panel.
No other Totem host was contacted for this hardware run.

## Evidence

- `metot-replay-camera.mp4` is the review-sized camera proof trimmed to the
  deterministic 28-frame replay, cropped to the physical panel, rotated 180
  degrees for reading orientation, converted to grayscale, and
  contrast/sharpness enhanced. The original 1920×1440, 30 fps capture was
  retained for local validation but deliberately omitted from Git history.
- `metot-replay-camera-contact-sheet.png` samples the enhanced physical capture.
- `metot-renderer-atlas.png` is the exact 28-frame atlas produced by the deployed
  `totem-screen replay-states` command on metot.

Replay completed all 28 frames successfully. The first panel update used a full
refresh; frames 2–20 were 19 partial updates; and frame 21, the twentieth
requested partial update, was promoted to a full refresh before the remaining
partial burst.

After replay, `totem-screen.service` was restored. Live verification reported all
five services active, both `/dev/spidev0.0` and `/dev/i2c-1` as character devices,
the V4 driver with `TOTEM_EINK_FULL_REFRESH_EVERY=20`, valid PiSugar2 telemetry,
encounter history mode `0600`, and zero recent screen/device-manager warnings.

The final identical Ansible deployment converged with `changed=0`, `failed=0`,
and `unreachable=0`.

## SHA-256

```text
379fa4f037d9bd869b5f8b649857e12828d3eeeba74ced4b65291545018a66de  metot-renderer-atlas.png
4ce672c399bba9fb50f5e2369414d63fffe1080cdbc95bc4c9ae99d53e677b2c  metot-replay-camera.mp4
cd0af131162671d16d99ca760f106da723ac47ac4591aee21fb21e4c9cfbb4ac  metot-replay-camera-contact-sheet.png
```
