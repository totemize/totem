# Roadmap: Totem Hardware Runtime

## Overview

Evolve the PR #22 Python hardware stack into a capability-oriented runtime
whose independently packaged drivers are discovered, matched, isolated,
supervised, and exposed without central device-type edits. Migration is
incremental: existing commands, routes, imports, configuration, and services
remain operational through compatibility facades.

## Phases

- [ ] **Phase 1: Capability-Oriented Hardware Runtime** — Replace the closed
  manager/registry hierarchy with a public, capability-oriented plugin runtime
  whose drivers are process-isolated by default.

## Phase Details

### Phase 1: Capability-Oriented Hardware Runtime

**Goal:** Deliver an independently versioned driver API, import-free plugin
catalog, deterministic compatibility resolver, resource broker, explicit
lifecycle, NIP-5D-shaped driver messaging, dual execution hosts, capability
services, and compatibility facades across the complete Python hardware
subsystem.
**Requirements:** HWR-01..04, SPI-01..06, CMP-01..04, ISO-01..07,
RUN-01..03, API-01..05, TST-01..04
**Depends on:** PR #22 commit `211f890b` and the driver-host feasibility spike
**Success Criteria** (what must be TRUE):

  1. A separately packaged fixture driver is discovered, matched, configured,
     and bound without editing Totem core or a central registry.

  2. The same functional conformance tests pass through isolated and in-process
     hosts; isolated driver failure cannot terminate the daemon and releases
     leases after child death, while an uncooperative in-process timeout marks
     the binding contaminated and retains leases until daemon restart.

  3. Exact matches, overrides, unsupported versions, missing prerequisites,
     resource conflicts, and ambiguous matches produce deterministic results
     with actionable evidence.

  4. Display, power, storage, NFC, Wi-Fi, and Bluetooth behavior is exposed via
     capability handles while existing imports, commands, routes, environment
     names, and systemd units continue to work through facades.

  5. Pi-class measurements establish an acceptable default IPC encoding and
     process granularity, with the decision recorded in the public contract.
**Plans:** 23/33 plans executed

Plans:

- [x] 01-01-PLAN.md
- [x] 01-02-PLAN.md
- [x] 01-03-PLAN.md
- [x] 01-04-PLAN.md
- [x] 01-05-PLAN.md
- [x] 01-06-PLAN.md
- [x] 01-07-PLAN.md
- [x] 01-08-PLAN.md
- [x] 01-09-PLAN.md
- [x] 01-10-PLAN.md
- [x] 01-11-PLAN.md
- [x] 01-12-PLAN.md
- [x] 01-13-PLAN.md
- [x] 01-14-PLAN.md
- [x] 01-15-PLAN.md
- [x] 01-16-PLAN.md
- [x] 01-17-PLAN.md
- [x] 01-18-PLAN.md
- [x] 01-19-PLAN.md
- [x] 01-20-PLAN.md
- [x] 01-21-PLAN.md
- [x] 01-22-PLAN.md
- [x] 01-23-PLAN.md
- [ ] 01-24-PLAN.md
- [ ] 01-25-PLAN.md
- [ ] 01-26-PLAN.md
- [ ] 01-27-PLAN.md
- [ ] 01-28-PLAN.md
- [ ] 01-29-PLAN.md
- [ ] 01-30-PLAN.md
- [ ] 01-31-PLAN.md
- [ ] 01-32-PLAN.md
- [ ] 01-33-PLAN.md

- [ ] TBD (run /gsd-plan-phase 1 to break down)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Capability-Oriented Hardware Runtime | 23/33 | In Progress|  |
