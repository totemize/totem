# Dual-Host Lifecycle

## Requirements

- Process isolation is the default. Global or per-plugin configuration may
  explicitly select the in-process host.
- Process and in-process adapters share capability schemas, validation,
  request/result/event behavior, and conformance fixtures.
- Functional parity does not imply containment parity. Only the process host
  promises hard termination, native-crash containment, and restart.
- An uncooperative in-process timeout contaminates the binding. Reject new
  work and retain its resource leases until controlled daemon restart.

## How to Build It

1. Define one provider interface and one logical `DriverHost` port. Implement
   `ProcessHost` and `InProcessHost` as adapters around that same interface;
   do not fork capability implementations by host mode.
2. Validate both adapters through the same canonical logical boundary. The
   spike encoded and decoded even in-process calls to prove Python object
   identity could not change behavior. Production may remove copies only if it
   retains the identical schema validator and shared conformance suite.
3. Serialize requests per binding unless a capability explicitly defines safe
   concurrency. Track pending request IDs, host generation, deadlines, event
   delivery, and stable public error codes.
4. In process mode, run the provider call on an invocation thread with a
   cooperative cancellation event. At the deadline:
   - signal cancellation;
   - wait a short, configured grace period;
   - if the thread exits, return `deadline_exceeded` and continue;
   - if it remains alive, mark the host `CONTAMINATED`, reject new work, retain
     all leases it may still touch, and request controlled daemon restart.
5. In isolated mode, at timeout or carrier failure:
   - remove pending correlations for the current generation;
   - terminate the child, escalating to kill if needed;
   - wait for confirmed exit;
   - release or reacquire leases through the resource broker;
   - spawn a new generation and resume only after `host.ready`.
6. Normalize caller-visible deadline and provider errors across modes. Keep
   containment state in health/supervision telemetry rather than pretending
   both hosts can recover identically.
7. Test native-style fatal behavior in a sacrificial daemon process. A fatal
   in-process plugin exit or extension fault is daemon-wide; the equivalent
   process-host failure must leave the daemon alive and restartable.

The in-process timeout decision must check liveness after cancellation:

```python
cancel.set()
thread.join(timeout=cancellation_grace)
if thread.is_alive():
    contaminated = True
    uncooperative_timeouts += 1
else:
    cooperative_cancellations += 1
return deadline_result(message)
```

The process-host replacement order is equally important:

```python
process.terminate()
try:
    process.wait(timeout=grace)
except subprocess.TimeoutExpired:
    process.kill()
    process.wait(timeout=grace)
release_leases_after_confirmed_exit()
spawn_next_generation()
```

## What to Avoid

- Do not call `join(timeout)` or `Future.cancel()` proof that Python code has
  stopped. A running Python thread cannot be forcibly cancelled safely.
- Do not release SPI, GPIO, I2C, serial, device-node, or adapter leases while
  timed-out in-process code remains alive.
- Do not start a replacement in-process provider beside a contaminated one.
- Do not describe the process host as a complete security sandbox. It is a
  crash, restart, and resource-ownership boundary; least-privilege policy is a
  separate implementation and verification concern.
- Do not create a faster direct-call contract for in-process extensions that
  bypasses carrier schemas and slowly diverges from isolated drivers.
- Do not hide mode-specific health. Operators must see generation, restart,
  contamination, cancellation, exit-code, and held-lease state.

## Constraints

- The shared harness produced identical normalized transcripts for eight cases
  in both modes: nested JSON, attachment, typed push, provider error, unknown
  request, short operation, deadline, and post-deadline request.
- A cooperative in-process timeout recovered normally. An uncooperative one
  left one live thread, contaminated the host, rejected follow-up work, and
  made resources unreleasable until daemon restart.
- The process-host hang terminated its child with observed exit `-15`, spawned
  the next generation, and completed follow-up work.
- A sacrificial `os._exit(86)` killed the in-process daemon probe. In process
  mode it killed only the child; the daemon restarted it and completed the next
  request.
- These failure semantics are `VALIDATED` locally. Device performance and
  least-privilege enforcement remain separate gates.

## Origin

Synthesized from spike: 003

Source files available in `sources/003-dual-host-contract/` and
`sources/_support/`.
