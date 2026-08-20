<script lang="ts">
  import { onMount } from "svelte";
  import {
    claim,
    loadSnapshot,
    nsecSigner,
    putConfig,
    putMetadata,
    streamOwner,
    waitForNip07,
    type Befriend,
    type OwnerFrame,
    type OwnerSigner,
    type PeerSnapshot,
    type PublicSnapshot,
    type Push,
  } from "./lib/totemd";

  type Screen = "home" | "totems" | "activity" | "settings";

  let screen = $state<Screen>("home");
  let snapshot = $state<PublicSnapshot | null>(null);
  let owner = $state<Required<Pick<OwnerFrame, "status" | "peers">> & { events: Push[] } | null>(null);
  let signer = $state<OwnerSigner | null>(null);
  let signerLabel = $state("");
  let nsec = $state("");
  let busy = $state(false);
  let ownerConnecting = $state(false);
  let error = $state("");
  let notice = $state("");
  let formsReady = false;
  let refreshPromise: Promise<void> | null = null;
  let ownerAbort: AbortController | null = null;

  let name = $state("");
  let displayName = $state("");
  let about = $state("");
  let picture = $state("");
  let website = $state("");
  let sync = $state(true);
  let befriend = $state<Befriend>("ask");

  const recentEvents = $derived(owner ? [...owner.events].reverse() : []);
  const totemPeers = $derived(
    owner?.peers.filter((peer) => peer.recognized || peer.probe_verdict === "candidate") ?? [],
  );

  $effect(() => {
    if (snapshot) document.title = `${snapshot.profile.name} · Totem`;
  });

  function fillForms(value: PublicSnapshot) {
    name = value.profile.name;
    displayName = value.profile.display_name ?? "";
    about = value.profile.about ?? "";
    picture = value.profile.picture ?? "";
    website = value.profile.website ?? "";
    sync = value.status.config.sync;
    befriend = value.status.config.befriend;
    formsReady = true;
  }

  function refresh(): Promise<void> {
    if (refreshPromise) return refreshPromise;
    refreshPromise = loadSnapshot()
      .then((value) => {
        snapshot = value;
        if (!formsReady) fillForms(value);
        error = "";
      })
      .catch((cause: unknown) => {
        error = cause instanceof Error ? cause.message : "Could not load Totem state.";
      })
      .finally(() => {
        refreshPromise = null;
      });
    return refreshPromise;
  }

  function short(value: string | null | undefined): string {
    if (!value) return "starting…";
    return value.length > 20 ? `${value.slice(0, 11)}…${value.slice(-7)}` : value;
  }

  function peerName(peer: PeerSnapshot): string {
    return peer.nip11_name?.replace(/^!Totem\s*/, "") || short(peer.npub);
  }

  function count(type: string): number {
    return snapshot?.status.events[type] ?? 0;
  }

  function stringField(event: Push, key: string): string | null {
    return typeof event[key] === "string" ? event[key] : null;
  }

  function eventText(event: Push): string {
    const peer = short(stringField(event, "npub"));
    switch (event.type) {
      case "totem.peer.seen": return `mesh peer seen · ${peer}`;
      case "totem.peer.gone": return `mesh peer left · ${peer}`;
      case "totem.peer.candidate": return `Totem candidate found · ${peer}`;
      case "totem.recognized": return `Totem recognized · ${peer}`;
      case "totem.sync.started": return `sync started · ${peer}`;
      case "totem.sync.done": return `sync ${stringField(event, "outcome") ?? "finished"} · ${peer}`;
      case "totem.owner.claimed": return "Totem claimed";
      case "totem.metadata.changed": return `profile published · ${stringField(event, "name") ?? "Totem"}`;
      case "totem.config.changed": return "engagement policy changed";
      default: return event.type;
    }
  }

  function eventDetail(event: Push): string {
    const summary = stringField(event, "summary");
    if (summary) return summary;
    const duration = typeof event.duration_ms === "number" ? `${event.duration_ms} ms` : "";
    const attempt = typeof event.attempt === "number" ? `attempt ${event.attempt}` : "";
    return [attempt, duration].filter(Boolean).join(" · ");
  }

  function acceptOwnerFrame(frame: OwnerFrame) {
    const events = frame.events
      ? frame.events
      : frame.event
        ? [...(owner?.events ?? []), frame.event].slice(-256)
        : (owner?.events ?? []);
    const first = owner === null;
    owner = { status: frame.status, peers: frame.peers, events };
    ownerConnecting = false;
    if (first) notice = "Owner controls unlocked.";
    void refresh();
  }

  function connectOwner() {
    if (!signer) return;
    ownerAbort?.abort();
    const controller = new AbortController();
    ownerAbort = controller;
    owner = null;
    ownerConnecting = true;
    error = "";
    void streamOwner(signer, controller.signal, acceptOwnerFrame)
      .then(() => {
        if (!controller.signal.aborted) {
          ownerConnecting = false;
          notice = "Owner event stream disconnected. Unlock again to reconnect.";
        }
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        ownerConnecting = false;
        owner = null;
        error = cause instanceof Error ? cause.message : "Could not unlock owner controls.";
      });
  }

  function selectSigner(next: OwnerSigner, pubkey: string) {
    if (signer?.clear && signer !== next) signer.clear();
    signer = next;
    signerLabel = short(pubkey);
    notice = `Signer selected · ${signerLabel}`;
    error = "";
    if (snapshot?.status.claimed) connectOwner();
  }

  async function useExtension() {
    busy = true;
    try {
      const next = await waitForNip07();
      selectSigner(next, await next.getPublicKey());
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not use browser extension.";
    } finally {
      busy = false;
    }
  }

  async function useNsec() {
    busy = true;
    try {
      const next = await nsecSigner(nsec.trim());
      const pubkey = await next.getPublicKey();
      nsec = "";
      selectSigner(next, pubkey);
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not use nsec.";
    } finally {
      busy = false;
    }
  }

  function forgetSigner() {
    ownerAbort?.abort();
    ownerAbort = null;
    signer?.clear?.();
    signer = null;
    signerLabel = "";
    owner = null;
    ownerConnecting = false;
    notice = "Signer forgotten.";
  }

  async function claimDevice() {
    if (!signer) return;
    const pubkey = await signer.getPublicKey();
    if (!window.confirm(`Claim this Totem with ${pubkey}?`)) return;
    busy = true;
    try {
      await claim(signer);
      formsReady = false;
      await refresh();
      screen = "settings";
      connectOwner();
      notice = "Totem claimed.";
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Claim failed.";
    } finally {
      busy = false;
    }
  }

  function optional(value: string): string | undefined {
    return value.trim() || undefined;
  }

  async function saveProfile() {
    if (!signer || !name.trim()) return;
    busy = true;
    try {
      await putMetadata(signer, {
        name: name.trim(),
        display_name: optional(displayName),
        about: optional(about),
        picture: optional(picture),
        website: optional(website),
      });
      await refresh();
      notice = "Public profile published.";
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Profile update failed.";
    } finally {
      busy = false;
    }
  }

  async function savePolicy() {
    if (!signer) return;
    busy = true;
    try {
      await putConfig(signer, { sync, befriend });
      await refresh();
      notice = "Engagement policy saved.";
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Policy update failed.";
    } finally {
      busy = false;
    }
  }

  function copy(value: string) {
    void navigator.clipboard.writeText(value).then(
      () => (notice = "Copied."),
      () => (error = "Clipboard access is unavailable."),
    );
  }

  onMount(() => {
    void refresh();
    const updates = new EventSource("/api/updates");
    updates.addEventListener("update", () => void refresh());
    const poll = window.setInterval(() => void refresh(), 15_000);
    window.addEventListener("pagehide", forgetSigner);
    return () => {
      updates.close();
      window.clearInterval(poll);
      window.removeEventListener("pagehide", forgetSigner);
      ownerAbort?.abort();
      signer?.clear?.();
    };
  });
</script>

{#snippet signerPicker()}
  <div class="signer-box">
    <p class="dim">Authorize with the owner key. The device key never enters this browser.</p>
    <div class="signer-actions">
      <button class="btn primary" type="button" disabled={busy} onclick={() => void useExtension()}>use browser extension</button>
      {#if signer}
        <button class="btn" type="button" onclick={forgetSigner}>forget {signerLabel}</button>
      {/if}
    </div>
    <details>
      <summary>development nsec</summary>
      <p class="warning">Kept only in this page's memory and cleared on navigation. Use a development key.</p>
      <form class="inline-form" onsubmit={(event) => { event.preventDefault(); void useNsec(); }}>
        <input type="text" name="username" autocomplete="username" value="totem-owner" hidden>
        <input type="password" name="nsec" placeholder="nsec1…" autocomplete="current-password" bind:value={nsec} required>
        <button class="btn" type="submit" disabled={busy}>use locally</button>
      </form>
    </details>
  </div>
{/snippet}

<div class="app">
  {#if !snapshot}
    <main class="screen setup center">
      <div class="mark">T</div>
      <p class="dim">loading Totem…</p>
    </main>
  {:else if !snapshot.status.claimed}
    <main class="screen setup center">
      <div class="mark">T</div>
      <h1>unclaimed totem</h1>
      <p class="dim">The first valid signer becomes this Totem's owner.</p>
      <div class="claim-panel">
        {@render signerPicker()}
        {#if signer}
          <button class="btn primary claim-button" type="button" disabled={busy} onclick={() => void claimDevice()}>claim this totem</button>
        {/if}
      </div>
      {#if error}<p class="error" role="alert">{error}</p>{/if}
      {#if notice}<p class="message" role="status">{notice}</p>{/if}
    </main>
  {:else}
    <header class="header">
      <button class="wordmark" type="button" onclick={() => (screen = "home")}>totem</button>
      <div class="status-line">
        {snapshot.status.fips.connected ? "FIPS connected" : "FIPS offline"}
        <span class:down={!snapshot.status.fips.connected} class="dot">●</span>
        {snapshot.status.recognized}/{snapshot.status.peers}
      </div>
    </header>

    {#if screen === "home"}
      <main class="screen">
        <section class="home-hero center">
          <div class="mark">T</div>
          <h1>{snapshot.profile.name}</h1>
          {#if snapshot.profile.about}<p class="dim about">{snapshot.profile.about}</p>{/if}
          <span class="tiny">totemd {snapshot.status.version} · up {Math.floor(snapshot.status.uptime_secs / 60)} min</span>
        </section>

        <section class="summary-grid" aria-label="Totem status">
          <div><strong>{snapshot.status.fips.mesh_size}</strong><span>mesh nodes</span></div>
          <div><strong>{snapshot.status.peers}</strong><span>direct peers</span></div>
          <div><strong>{snapshot.status.recognized}</strong><span>recognized</span></div>
          <div><strong>{count("totem.sync.done")}</strong><span>sync rounds</span></div>
        </section>

        <section class="public-info">
          <h2>local relay</h2>
          <button class="code-button" type="button" title="copy relay URL" onclick={() => copy(snapshot!.relay_url)}>{snapshot.relay_url}</button>
          <h2>device identity</h2>
          <button class="code-button" type="button" title="copy npub" onclick={() => snapshot!.status.fips.npub && copy(snapshot!.status.fips.npub)}>{snapshot.status.fips.npub ?? "starting…"}</button>
        </section>

        <section class="activity center">
          <h2 class="activity-title">recent activity</h2>
          {#if owner}
            {#each recentEvents.slice(0, 3) as event}
              <div class="tiny activity-line">{eventText(event)}</div>
            {:else}
              <p class="dim">no activity in this daemon run</p>
            {/each}
            <button class="see-all" type="button" onclick={() => (screen = "activity")}>view all ›</button>
          {:else}
            <p class="dim">unlock owner controls to view device activity</p>
            <button class="btn" type="button" onclick={() => (screen = "settings")}>unlock</button>
          {/if}
        </section>
      </main>
    {:else if screen === "totems"}
      <main class="screen">
        <h1 class="screen-title">current totems</h1>
        {#if owner}
          {#each totemPeers as peer (peer.npub)}
            <div class="item">
              <div class="avatar"></div>
              <span class="label">{peerName(peer)}</span>
              <span class="hint">{peer.recognized ? "recognized" : "candidate"}{peer.sync_state ? ` · ${peer.sync_state}` : ""}</span>
            </div>
          {:else}
            <div class="empty dim">no Totems connected right now</div>
          {/each}
        {:else}
          <div class="locked center">
            <p class="dim">Current peer identities are owner-only.</p>
            <button class="btn" type="button" onclick={() => (screen = "settings")}>unlock owner controls</button>
          </div>
        {/if}
      </main>
    {:else if screen === "activity"}
      <main class="screen">
        <button class="back" type="button" onclick={() => (screen = "home")}><span>←</span> recent activity</button>
        {#if owner}
          {#each recentEvents as event}
            <div class="event-row">
              <span>{eventText(event)}</span>
              {#if eventDetail(event)}<small>{eventDetail(event)}</small>{/if}
            </div>
          {:else}
            <div class="empty dim">no activity in this daemon run</div>
          {/each}
        {/if}
      </main>
    {:else}
      <main class="screen settings-screen">
        <div class="identity-row">
          <button class="chip" type="button" onclick={() => snapshot!.status.fips.npub && copy(snapshot!.status.fips.npub)}>{short(snapshot.status.fips.npub)}</button>
          <span class="at">at</span>
          <button class="chip" type="button" onclick={() => copy(snapshot!.relay_url)}>{snapshot.relay_url}</button>
        </div>

        <section>
          <h2 class="section-label">engagement policy</h2>
          <div class="kv-row"><span>sync</span><span class="value">{snapshot.status.config.sync ? "every recognized Totem" : "friends only"}</span></div>
          <div class="kv-row"><span>friendship</span><span class="value">{snapshot.status.config.befriend}</span></div>
        </section>

        <section class="owner-section">
          <h2 class="section-label">owner controls</h2>
          {#if owner}
            <div class="owner-unlocked">
              <span class="tiny">unlocked · {signerLabel}</span>
              <button class="btn" type="button" onclick={forgetSigner}>lock</button>
            </div>

            <form class="owner-form" onsubmit={(event) => { event.preventDefault(); void saveProfile(); }}>
              <h3>public profile</h3>
              <label>name <input maxlength="64" bind:value={name} required></label>
              <label>display name <input maxlength="128" bind:value={displayName}></label>
              <label>about <textarea maxlength="1024" rows="3" bind:value={about}></textarea></label>
              <label>picture URL <input type="url" maxlength="2048" bind:value={picture}></label>
              <label>website <input type="url" maxlength="2048" bind:value={website}></label>
              <button class="btn primary" type="submit" disabled={busy}>publish profile</button>
            </form>

            <form class="owner-form" onsubmit={(event) => { event.preventDefault(); void savePolicy(); }}>
              <h3>engagement policy</h3>
              <label class="check"><input type="checkbox" bind:checked={sync}> sync every recognized Totem</label>
              <label>friendship
                <select bind:value={befriend}>
                  <option value="ask">ask</option>
                  <option value="auto">automatic</option>
                  <option value="never">never</option>
                </select>
              </label>
              <button class="btn primary" type="submit" disabled={busy}>save policy</button>
            </form>
          {:else}
            {@render signerPicker()}
            {#if signer && !ownerConnecting}
              <button class="btn primary unlock-button" type="button" onclick={connectOwner}>unlock owner controls</button>
            {/if}
            {#if ownerConnecting}<p class="dim">waiting for owner signature…</p>{/if}
          {/if}
        </section>

        <footer class="tiny">totemd {snapshot.status.version}</footer>
      </main>
    {/if}

    <nav class="tabbar" aria-label="Main navigation">
      <button class:on={screen === "totems"} type="button" onclick={() => (screen = "totems")}>Totems</button>
      <button class:on={screen === "home" || screen === "activity"} type="button" onclick={() => (screen = "home")}>Home</button>
      <button class:on={screen === "settings"} type="button" onclick={() => (screen = "settings")}>Settings</button>
    </nav>

    {#if error}<div class="message-bar error" role="alert">{error}</div>
    {:else if notice}<div class="message-bar" role="status">{notice}</div>{/if}
  {/if}
</div>
