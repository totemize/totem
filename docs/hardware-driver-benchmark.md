# Pi Driver-Host Benchmark and Cutover Gate

This is a manual allocation gate.  Do not contact a device, change a service,
or pass `--run-hardware` unless an operator has explicitly allocated the
target and approved the rollback procedure.

## What the pinned workload measures

For every allocated armv6l, armv7l, and aarch64 target, capture two independent
records: the default provider-group run and a per-binding-group run.  Both use
the same pinned workload from `scripts/benchmark_driver_host.py`:

- realistic provider imports plus the canonical JSON process host;
- startup-to-`host.ready`, steady Linux PSS from `/proc/<pid>/smaps_rollup`
  (or a clearly labeled RSS fallback);
- p50/p95 control request latency with 20 samples;
- a raw 4,000-byte display-frame attachment;
- 100-event load, crash and uncooperative-hang recovery, generation advances,
  post-death lease release, and zero leaked workers/threads/sockets;
- installed Python/runtime/package versions, execution mode, grouping, target
  allocation reference, and completed rollback evidence.

The command records no credentials, descriptors, secrets, or configuration
values.  It validates evidence only; an operator wrapper performs the actual
runtime workload on the allocated device.

```sh
# Safe controller-only contract checks; no hardware is contacted.
.venv/bin/python -m pytest tests/hardware/test_driver_host_bench.py --collect-only -q
.venv/bin/python scripts/benchmark_driver_host.py --self-test
.venv/bin/python scripts/benchmark_driver_host.py --workload

# Allocated-device evidence validation.  Repeat --evidence-json for provider
# and binding grouping records from exactly this approved target/allocation.
# The controller-local trust store is JSON: {"allocations": {"<ticket>":
# {"target": "...", "device_identity": "...", "key_id": "...",
# "hmac_key_b64": "..."}}}.  It is provisioned out of band and must not be
# copied into an evidence file.
.venv/bin/python scripts/benchmark_driver_host.py \
  --run-hardware --target <approved-target> --allocation <ticket> \
  --trusted-allocations <controller-allocation-store.json> \
  --evidence-json provider.json --evidence-json binding.json
```

The pytest hardware harness is additionally guarded by `--run-hardware` and
explicit `TOTEM_BENCHMARK_TARGET`/`TOTEM_BENCHMARK_ALLOCATION` values.  Without
those switches and values it is skipped and performs no device, network, GPIO,
I2C, SPI, USB, serial, radio, or service operation.

## Fail-closed acceptance matrix

An architecture is accepted only when both grouping rows validate with every
field present.  A missing metric, a non-PSS source mislabeled as PSS, incomplete
crash/hang recovery, no generation advance, remaining lease, incomplete cleanup,
or missing rollback blocks acceptance.

| Architecture | Provider group | Per-binding group | Accepted | Evidence reference |
|---|---:|---:|---:|---|
| armv6l | pending | pending | no | pending explicit allocation |
| armv7l | pending | pending | no | pending explicit allocation |
| aarch64 | pending | pending | no | pending explicit allocation |

Controller-only or synthetic output is never a substitute for these rows and
cannot be copied into the matrix as Pi acceptance.

## Manual cutover and rollback

After all six matrix records validate and a maintainer reviews the architecture
trade-off, schedule a separate deployed-default cutover:

1. Capture the current package/configuration/service state and a recovery owner.
2. Deploy the candidate under the existing compatibility command/service names;
   do not mutate defaults before the rollback path is ready.
3. Exercise the preserved commands, routes, and loopback bus; induce a child
   crash and hang through the approved local fault mechanism; confirm recovery,
   generation change, carrier closure, and post-death lease release.
4. If any observation fails, restore the captured package/configuration and
   restart only under the approved operator procedure.  Record the outcome.
5. Mark the cutover accepted only after successful rollback rehearsal or a
   documented equivalent recovery proof for every required architecture.

Process isolation is not an OS sandbox or a supply-chain trust decision.  The
deployment review still owns systemd hardening, device-node access, D-Bus policy,
and package trust.
