---
spike: 003
name: dual-host-contract
type: standard
validates: "Given one capability provider and conformance suite, when the provider runs through in-process and isolated-process hosts, then functional envelopes match exactly while timeout, crash, restart, and resource-release guarantees remain explicitly mode-specific."
verdict: VALIDATED
related: [001a, 001b, 002a, 002b]
tags: [host, conformance, lifecycle, process, threading, isolation]
---

# Spike 003: Dual-host contract and failure parity

## What This Validates

Given one capability provider and conformance suite, when the provider runs
through in-process and isolated-process hosts, then functional envelopes match
exactly while timeout, crash, restart, and resource-release guarantees remain
explicitly mode-specific.

## Research

Python's [`threading` documentation](https://docs.python.org/3.9/library/threading.html)
is unambiguous: threads cannot be destroyed, stopped, suspended, resumed, or
interrupted. `join(timeout)` only stops waiting; callers must check
`is_alive()`. The
[`concurrent.futures` documentation](https://docs.python.org/3.9/library/concurrent.futures.html)
similarly says a running call cannot be cancelled. In-process deadlines are
therefore cooperative. Releasing an SPI/GPIO/adapter lease while timed-out
plugin code is still running would permit two owners to touch the same
hardware and is unsafe.

Python's [`subprocess` documentation](https://docs.python.org/3.9/library/subprocess.html)
provides `terminate()` and `kill()` for child processes and explicitly shows
killing a child after a timeout. A process host can enforce a hard boundary,
wait for death, release leases, and start a new generation. This is a fault
boundary, not a claim that the subprocess is a complete security sandbox.

| Approach | Functional consistency | Failure containment | Status |
|----------|------------------------|---------------------|--------|
| Two adapters, one serialized logical contract | Same envelopes and conformance fixtures | Mode-specific and explicit | Chosen |
| Direct Python-only in-process API | Fastest path | Contract can drift from IPC; Python objects leak into SPI | Rejected |
| Pretend thread timeout equals process termination | Superficially similar result | Leaves code running and resources unsafe | Rejected |
| Process-only runtime | Strong hard-failure behavior | Removes the operator-selected in-process extension mode | Conflicts with requirement |

The in-process adapter deliberately encodes and decodes through the same
canonical JSON framing before invoking the provider. This costs work but makes
the shared contract testable; a later optimized adapter may skip physical byte
copies only if the same schema validator/conformance suite remains mandatory.

## How to Run

From the repository root:

```bash
python3 .planning/spikes/003-dual-host-contract/run.py
```

No hardware or third-party package is required. Native-style crash cases run
only inside sacrificial Python processes.

## What to Expect

- Both hosts produce identical transcripts for nested JSON, a binary display
  frame, a typed event, provider error, unknown request, short operation,
  deadline result, and post-deadline request.
- A cooperative in-process deadline stops cleanly; the process mode enforces
  the same caller result by replacing its child.
- An uncooperative in-process call marks the host contaminated and blocks new
  work; its resources cannot be reassigned until daemon restart.
- The same process-host hang is terminated, its child is replaced, resources
  become releasable, and the next request succeeds.
- A provider `os._exit(86)` kills the sacrificial in-process daemon. In process
  mode it kills only the driver child; the sacrificial daemon restarts it and
  completes a follow-up request.

## Observability

`results.json` includes the exact functional check names, host generations,
restart and cancellation counts, deadline/follow-up envelopes, contamination
state, resource-release decisions, and crash-probe exit codes. The harness
asserts every expected transition before writing a result.

## Investigation Trail

1. Defined one fixture provider; neither host has a separate capability
   implementation.
2. Forced both hosts across the 002a serializer and attachment validator so
   equality is semantic, not an assumption about Python calls.
3. Added a cooperative deadline and post-timeout request to prove both modes
   can expose the same normal contract through different recovery mechanisms.
4. Added an uncooperative hang to test the boundary the normal conformance case
   cannot reveal.
5. Moved `os._exit` tests into sacrificial processes so real process-wide
   failure behavior is measured without risking the spike runner.
6. Repeated the entire functional/hang/crash run three additional times and
   checked the process table; every assertion remained stable and no worker or
   crash-probe process survived teardown.

## Results

**VALIDATED, with an intentional containment asymmetry.** Both adapters passed
eight functional cases and produced identical normalized transcripts: nested
JSON, raw display attachment, typed push, structured provider failure, unknown
request, short operation, deadline result, and a successful follow-up. The
in-process deadline cooperatively stopped its invocation thread. The process
host returned the same deadline envelope after terminating generation 1,
starting generation 2, and completing the follow-up there.

The uncooperative case proves why parity must stop at the functional contract.
After its deadline, the in-process invocation thread was still alive; the host
was marked contaminated, rejected the next request, could not safely release
resources, and required daemon restart. The isolated host terminated its child
(`SIGTERM`, observed as `-15`), released the failure domain, started a new child,
and completed the next request.

The sacrificial native-style crash made the difference stronger. Calling
`os._exit(86)` inside the in-process provider ended the whole probe with code
86. In isolated mode, the daemon probe stayed alive, observed driver exit 86,
restarted the child once, and completed a follow-up request. `os._exit` is a
stand-in for process-fatal native extension behavior; the relevant containment
boundary is the same.

The production contract must therefore promise identical capability behavior
and caller-facing deadline errors, while documenting stronger hard-failure and
lease-release guarantees only for process mode. In-process execution remains a
deliberate trust/performance opt-in, not an equivalent isolation mode.
