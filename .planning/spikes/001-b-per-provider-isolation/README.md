---
spike: 001b
name: per-provider-isolation
type: comparison
validates: "Given eight logical hardware bindings, when one executable child multiplexes every binding from a provider, then startup and memory cost are amortized while the provider-wide crash domain is measured."
verdict: PARTIAL
related: [001a]
tags: [process, isolation, topology, python]
---

# Spike 001b: Per-provider isolation

## What This Validates

Given eight logical hardware bindings, when one executable child multiplexes
every binding from a provider, then startup and memory cost are amortized while
the provider-wide crash domain is measured.

## Research

The carrier and measurement choices are shared with 001a: Python
[`subprocess.Popen`](https://docs.python.org/3/library/subprocess.html) creates
an actual executable boundary; Linux
[`smaps_rollup`](https://www.kernel.org/doc/html/latest/filesystems/proc.html)
provides PSS when available; other hosts use a labelled RSS fallback. Reusing
the exact worker and request loop prevents protocol implementation differences
from contaminating the topology comparison.

| Approach | Advantages | Costs | Status |
|----------|------------|-------|--------|
| One host per provider distribution | Amortizes interpreter and plugin imports; provider is a natural package/version/trust unit | All of that provider's bindings fate-share | Chosen for 001b |
| One host per binding | One binding per failure and restart domain | Process and supervision count scales with bindings | Measured in 001a |
| Shared fleet-wide plugin host | Lowest interpreter count | Unrelated providers and trust domains fate-share | Rejected |

The paired runner alternates which topology runs first over five trials. This
does not manufacture Pi-grade results, but it reduces the chance that one warm
or cold local sample decides the recommendation.

## How to Run

Run the provider topology alone, then the repeated comparison:

```bash
python3 .planning/spikes/001-b-per-provider-isolation/run.py
python3 .planning/spikes/001-b-per-provider-isolation/compare.py
```

Both accept `--bindings` and `--rounds`; `compare.py` also accepts `--trials`.

## What to Expect

- One child hosts all eight logical bindings.
- All 1,600 requests succeed before failure injection.
- Terminating the child removes all eight bindings; there are no unaffected
  bindings to probe.
- Replacing the provider host restores and verifies every binding.
- `comparison.json` reports medians and per-binding/per-provider cost ratios.

## Observability

`results.json` contains the standalone sample. `comparison.json` contains five
paired samples reduced to median startup, memory, latency, recovery, failure
counts, and ratios. Both carry schema IDs and the measurement scope.

## Investigation Trail

1. Kept the worker executable, message shape, binding count, request count,
   failure signal, and recovery checks identical to 001a.
2. Made one child advertise and route all binding IDs; this changes only the
   ownership/failure grouping.
3. Added alternating repeated trials for a head-to-head result instead of
   comparing unrelated one-off runs.
4. Five paired trials preserved the topology distinction every time: 001a
   lost one binding and passed seven survivor checks; 001b lost all eight and
   restored all eight after replacing the host.

## Results

**PARTIAL, and the provisional comparison winner for the default topology.**
The standalone provider host completed all 1,600 requests, then lost and
recovered all eight bindings as predicted. In five paired trials, the median
provider topology used one process and 11,872 KiB summed fallback RSS versus
eight processes and 94,768 KiB for per-binding isolation: a 7.982× difference.
Median startup to all bindings ready was 19.264 ms versus 26.016 ms. Median
round-trip latency was 0.012625 ms versus 0.018417 ms; this tiny local pipe
difference is not decision-grade.

The decisive tradeoff is structural, not the desktop timings. A provider
distribution is already one code/version/trust unit, so one isolated process
per provider scales better for the default. Per-binding processes should remain
an optional grouping override for unstable drivers, independently restartable
resources, or deployments that value the smaller blast radius over memory.

The verdict remains `PARTIAL` because macOS RSS may double-count shared pages
and the empty worker omits real imports. Repeat `compare.py` on Pi-class Linux,
where the harness automatically selects PSS, before locking the production
default or budgets.
