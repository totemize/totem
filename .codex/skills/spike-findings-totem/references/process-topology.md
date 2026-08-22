# Process Topology

## Requirements

- Process isolation is the default for every Python hardware capability.
- Operators may override execution globally or per plugin; process grouping is
  a separate setting from process-versus-in-process hosting.
- Independently installed drivers execute as external programs. Cataloging
  must not import plugin code into the daemon.
- Resource ownership and failure domains must be explicit. A lease is released
  only after its owner is known to have stopped.
- Current measurements are local evidence. Lock the fleet default only after
  armv6l/armv7l and aarch64 runs with realistic imports and Linux PSS.

## How to Build It

1. Treat a provider distribution as the default process group. Resolve all
   compatible bindings first, then group them by provider identity and version.
2. Launch the provider's declared executable with `subprocess.Popen`; pass only
   bounded configuration, inherited descriptors, or brokered resource handles.
   Do not import its Python package in the daemon.
3. Require a versioned `host.ready` handshake before publishing any binding.
   Track a monotonically increasing host generation so results from a dead
   generation cannot satisfy new pending requests.
4. Maintain an explicit `binding_id -> host generation` routing map. A provider
   process may multiplex many bindings, but every message still names the
   resolved binding.
5. Support `process_group = "binding"` as an override for unstable drivers,
   independently restartable resources, or installations that accept the
   additional interpreter cost for a smaller crash domain.
6. On timeout or crash, terminate the child, escalate to kill if required, wait
   for confirmed exit, invalidate all bindings in that group, release their
   leases, spawn the next generation, and rebind deterministically.
7. Measure startup, recovery, request latency, and memory with the same
   workload. On Linux, sum PSS from `/proc/<pid>/smaps_rollup`; label RSS as a
   fallback and never compare it directly with Pi PSS.

The spike's grouping rule is intentionally small and data-driven:

```python
def groups_for(topology, binding_ids):
    if topology == "per-binding":
        return [(binding,) for binding in binding_ids]
    if topology == "per-provider":
        return [tuple(binding_ids)]
    raise ValueError(f"unsupported topology: {topology}")
```

The external boundary is an executable, not a Python object bootstrap:

```python
command = [sys.executable, str(worker)]
process = subprocess.Popen(
    command,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
```

Replace the spike's line-delimited pipe protocol with the framed Unix-socket
carrier in `driver-ipc.md`; retain its readiness, failure injection, recovery,
and PSS measurement patterns as production acceptance tests.

## What to Avoid

- Do not create one fleet-wide plugin process. It combines unrelated package,
  version, trust, and crash domains.
- Do not use `multiprocessing` or pickle at the public SPI boundary. They couple
  the daemon to Python object import and executable serialization behavior.
- Do not make one process per binding the unconditional default. Eight empty
  local interpreters used about eight times the summed RSS of one provider
  process in the controlled comparison.
- Do not treat a successful child spawn as a usable binding; wait for the
  versioned ready message and complete resource acquisition.
- Do not release resources when a child is merely presumed dead. Confirm exit
  and close the carrier first.
- Do not convert the local macOS RSS or tiny pipe-latency differences into
  fleet budgets.

## Constraints

- Across five local paired trials with eight empty Python bindings, per-binding
  grouping used 8 processes and median summed RSS of 94,768 KiB; per-provider
  grouping used 1 process and 11,872 KiB. RSS may double-count shared pages.
- The injected per-binding crash lost 1 binding; the per-provider crash lost
  all 8. Both recovered their expected failure domains.
- Median startup was 26.016 ms per-binding and 19.264 ms per-provider on the
  local macOS/Python 3.9 controller. These are not Pi acceptance thresholds.
- Representative plugin imports, device-node descriptors, D-Bus connections,
  and Linux PSS were not part of these experiments.

## Origin

Synthesized from spikes: 001a, 001b

Source files available in:
`sources/001-a-per-binding-isolation/`,
`sources/001-b-per-provider-isolation/`, and `sources/_support/`.
