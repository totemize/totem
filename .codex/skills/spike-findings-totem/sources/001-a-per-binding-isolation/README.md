---
spike: 001a
name: per-binding-isolation
type: comparison
validates: "Given eight logical hardware bindings, when each binding runs in its own executable child, then a child crash removes exactly one binding and the topology's startup, memory, latency, and recovery costs are observable."
verdict: PARTIAL
related: [001b]
tags: [process, isolation, topology, python]
---

# Spike 001a: Per-binding isolation

## What This Validates

Given eight logical hardware bindings, when each binding runs in its own
executable child, then a child crash removes exactly one binding and the
topology's startup, memory, latency, and recovery costs are observable.

## Research

Python's [`subprocess` documentation](https://docs.python.org/3/library/subprocess.html)
defines `Popen` as the lower-level interface for executing a child program and
supports explicit stdin/stdout pipes. It maps closely to the proposed runtime:
an independently installed plugin is loaded by a different interpreter, not
imported into the daemon. `multiprocessing` could simplify Python object
launching, but its Python-specific bootstrap and serialization are exactly the
coupling the public driver boundary is intended to avoid.

Linux exposes aggregate mapping data through
[`/proc/PID/smaps_rollup`](https://www.kernel.org/doc/html/latest/filesystems/proc.html),
including proportional set size (PSS), which apportions shared pages instead
of charging every interpreter for all shared mappings. Python's
[`resource.getrusage`](https://docs.python.org/3/library/resource.html) reports
maximum resident set size rather than the current live footprint, so it is not
used. On non-Linux systems the harness falls back to current RSS from `ps` and
labels the possible shared-page double counting.

| Approach | Mechanism | Advantages | Costs | Status |
|----------|-----------|------------|-------|--------|
| One executable per binding | `subprocess.Popen` | Smallest crash and restart domain; direct resource ownership | Interpreter and supervision cost scales with binding count | Chosen for 001a |
| One executable per provider | `subprocess.Popen` with multiplexing | Amortizes interpreter and plugin imports | Every provider binding fate-shares | Compared in 001b |
| Python `multiprocessing` workers | `spawn` context | Convenient Python API | Python-specific bootstrap; tempts object serialization across the SPI | Not chosen |

The worker deliberately imports only the standard library. These measurements
characterize topology overhead; real driver imports and hardware calls require
a separate Pi-class acceptance run.

## How to Run

From the repository root:

```bash
python3 .planning/spikes/001-a-per-binding-isolation/run.py
```

Use `--bindings N --rounds N` to change the load. The full machine-readable
result is written to `results.json`.

## What to Expect

- Eight child interpreters become ready.
- Every logical binding completes 200 correlated round trips.
- Terminating one host removes one binding; the other seven still answer.
- A replacement host becomes ready and the lost binding answers again.
- Linux reports PSS; other systems report the explicitly labelled RSS fallback.

## Observability

`results.json` records platform and Python version, startup-to-ready time,
process count, current memory by host, median/p95/max round-trip latency, the
forced-failure blast radius, survivor checks, and replacement readiness.

## Investigation Trail

1. Selected an executable child rather than `multiprocessing` so the harness
   exercises the same package/import boundary required of third-party drivers.
2. Rejected `ru_maxrss` because it is a high-water mark, not a current process
   measurement. Added Linux PSS with a clearly named RSS fallback.
3. Added a forced termination, survivor pings, replacement, and post-recovery
   ping so a successful steady-state benchmark cannot hide the failure domain.
4. Re-ran the failure path at 2 and 16 bindings. Both retained the one-binding
   blast radius, and no worker remained after teardown. Summed fallback RSS
   rose from 22,720 KiB at two empty hosts to 188,480 KiB at sixteen, confirming
   the expected approximately linear interpreter cost on this machine.

## Results

**PARTIAL.** The behavioral premise is validated locally: all 1,600 correlated
requests completed; forcibly terminating one of eight hosts removed exactly
one binding; all seven survivors answered; and a replacement was ready in
18.560 ms. Startup to all eight ready was 26.529 ms. Median/p95 pipe round-trip
latency was 0.019/0.036635 ms.

The eight empty CPython processes summed to 93,728 KiB of RSS on macOS. That is
not a Pi acceptance number and may double-count shared pages, but the 2/8/16
binding runs demonstrate that the host count and resident-memory charge grow
with binding count. The topology earns `PARTIAL`, not `VALIDATED`, until the
same harness reports Linux PSS and realistic driver imports on Pi-class
hardware. Its proven advantage is the one-binding failure and restart domain.
