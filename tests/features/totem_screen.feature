Feature: Continuous Totem e-ink presentation
  The screen reconciles authoritative local snapshots after boot and projects
  them into a deliberately closed, glyph-safe scene catalog.

  Scenario Outline: Every permitted runtime scene renders its exact sequence
    Given a reconciled snapshot that derives <scene>
    When the scene sequence is rendered
    Then every configured frame is drawn as crisp one-bit vector ink
    And the header and footer remain visible

    Examples:
      | scene                 |
      | idle                  |
      | alone_idle            |
      | peer_seen             |
      | candidate             |
      | newly_recognized      |
      | returning_recognized  |
      | sync_running          |
      | sync_succeeded        |
      | sync_interrupted      |
      | non_totem_peer        |
      | charging              |
      | low_battery           |
      | critical_battery      |
      | mesh_degraded         |

  Scenario: Orthogonal facts are arbitrated by priority
    Given social, sync, mesh, and power facts can coexist
    When the projector selects the main content scene
    Then critical battery preempts every other scene
    And social payoff preempts active exchange
    And lower-priority facts remain visible in persistent header or footer ink

  Scenario: SSE is a notification and never state authority
    Given the lossy event stream sends a notification
    When the screen wakes
    Then it fetches fresh status, peers, DeviceManager health, and UPS facts
    And it derives the scene only from that reconciled snapshot

  Scenario: A quiet event stream still refreshes persistent facts
    Given the SSE connection remains silent
    When the configured poll interval elapses
    Then the screen reconciles another complete snapshot

  Scenario: A lost event stream reconnects safely
    Given the SSE connection ends or cannot connect
    When the configured reconnect delay elapses
    Then a fresh stream is opened
    And a complete snapshot is fetched before any new scene is selected

  Scenario: Fast encounter progress is coalesced
    Given peer seen and candidate snapshots arrive within the coalescing window
    When the burst becomes quiet
    Then only the newest authoritative candidate scene is selected

  Scenario: Social payoff has a minimum dwell
    Given a newly recognized scene is visible
    When a lower-priority sync-running snapshot arrives
    Then recognition remains visible for its configured minimum dwell
    And sync begins afterward

  Scenario: Process restart does not replay stale payoffs
    Given the first snapshot already contains recognition or a terminal sync
    When the runtime projector is seeded
    Then those existing one-shot tokens are treated as consumed
    And a later encounter or sync attempt can still produce a new payoff

  Scenario: Ambient copy distinguishes company from loneliness
    Given live peer rows include recognized friends
    When no higher-priority scene remains
    Then the ambient scene is idle rather than alone_idle
    And departed friends do not prevent alone_idle

  Scenario: A departed sync is reconciled without reviving its peer
    Given peers.get retains a bounded row with present false and cancelled sync
    When the projector reconciles that tombstone
    Then it emits the sync_interrupted payoff once
    And it excludes that row from live peer, recognition, and activity scenes

  Scenario: Header and footer communicate persistent facts
    Given config.device_name, FIPS status, UPS charge, and count facts
    When a runtime frame is drawn
    Then the device name is at the left of the header
    And the FIPS icon is left of the rightmost battery icon
    And the footer orders mesh size / direct peers / recognized friends, with notes rightmost

  Scenario: Every state can be proofed on hardware
    Given the replay-states command
    When an operator runs it on the display device
    Then every frame is logged with a deterministic ordinal
    And its first frame seeds a full refresh before later partial refreshes
    And an optional PNG atlas can be exported

  Scenario: Captions belong to authoritative scene admissions
    Given every runtime scene has ten approved captions
    When a scene admission chooses one caption
    Then repeated snapshots and face frames retain that caption
    And words appear as stable prefixes on their independent clock
    And a later admission avoids immediately repeating the same caption

  Scenario: Every caption can be proofed without a long hardware replay
    Given the proof-captions command
    When an operator exports its deterministic atlas
    Then all 140 complete captions are rendered
    And representative word prefixes and every face sequence are included
    And captions remain inside the fixed band above the unchanged footer

  Scenario: Boot retains its lifecycle without avoidable full resets
    Given the legacy splash and readiness checklist
    When each boot transition is rendered
    Then the first boot frame seeds a full refresh
    And every later checklist and idle transition requests partial refresh
