# Spike Conventions

Patterns and stack choices established across spike sessions. New spikes
follow these unless the question requires otherwise.

## Stack

- Use the repository's Python floor (3.9) and standard library for the default
  harness. A spike must not silently validate only a newer controller runtime.
- Keep third-party comparison dependencies in the ignored
  `.planning/spikes/.venv`; pin the exact version in the variant directory and
  record runtime/architecture compatibility in its README.
- Hardware-runtime protocol fixtures use the same NIP-5D-shaped logical model
  as `totemd`: typed JSON-compatible objects, correlated `.result` messages,
  structured `ok`/error outcomes, and unsolicited typed pushes.

## Structure

- A variant lives at `.planning/spikes/NNN-a-name/` or
  `.planning/spikes/NNN-name/` with `README.md`, `run.py`, and committed
  `results.json`.
- Code shared by comparison variants lives under `.planning/spikes/_support/`.
  Variant runners remain one-command entry points from the repository root.
- Machine-readable results have a versioned `schema` field, identify platform
  and runtime when measurements depend on them, and name every conformance
  case rather than reporting only a pass count.

## Patterns

- Change one variable across comparison variants and reuse fixtures, failure
  injection, load, limits, and measurement code. Run repeated trials with
  rotated order before interpreting small timing differences.
- Test malformed, oversized, fragmented, interrupted, and recovery paths
  before assigning a verdict; a steady-state happy path is insufficient.
- Run process-fatal experiments in sacrificial subprocesses and assert that no
  worker survives teardown.
- Keep control messages in the strict JSON value subset across encodings.
  Binary data uses explicit, bounded, checksummed raw attachments.
- Label desktop RSS/timing results as local evidence. Fleet conclusions require
  Linux PSS and representative armv6l/armv7l/aarch64 runs; no bench device is
  contacted without allocation.
- Record functional parity and containment guarantees separately. The same
  caller envelope does not imply the same hard-failure boundary.

## Tools & Libraries

- Prefer `subprocess.Popen`, `socket.AF_UNIX`, `struct` network byte order,
  `threading`, and canonical `json` from the Python standard library.
- On Linux, use `/proc/PID/smaps_rollup` PSS for multi-process memory. Elsewhere
  use a clearly labelled current-RSS fallback and do not compare it directly to
  Pi PSS.
- `msgpack==1.1.2` is retained only for codec comparison under Python 3.9. It is
  not the selected v1 runtime dependency; current 1.2.x requires Python 3.10,
  and the fleet's armv6/armv7 installation path remains unverified.
