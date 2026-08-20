<script lang="ts">
  import NoteRow from "$lib/components/NoteRow.svelte";
  import { relativeTime, shortNpub } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const info = $derived(store.state.landing);
  const peer = $derived(store.state.peers.find((p) => p.info.pubkey === info?.pubkey));
  const notes = $derived(store.state.notes.filter((n) => n.author?.pubkey === info?.pubkey));
  const encounters = $derived(store.state.encounterLog.filter((e) => e.peer.pubkey === info?.pubkey));
</script>

<div class="screen">
  <button class="back" onclick={() => store.closeLanding()} ><span class="arr">←</span> back</button>
  <div class="pad center" style="padding:24px">
    <div class="mark">T</div>
    <h1 style="font-size:18px">{info?.name ?? "unknown"}</h1>
    <div class="tiny" style="margin-top:8px">{info ? shortNpub(info.pubkey) : ""} · {info?.relayUrl ?? ""}</div>
    {#if peer?.connected}
      <div class="tiny" style="margin-top:4px">connected · {peer.connected.transport}</div>
    {/if}
  </div>

  {#if encounters.length}
    <div class="section-label">encounters</div>
    {#each encounters as e, i (i)}
      <div class="kv-row sub">
        <span>{relativeTime(e.at)}</span>
        <span class="value">{e.transport} ·
          {#if e.verdict === "failed"}challenge failed{:else if e.received || e.sent}<span class="arr">↓</span>{e.received.toLocaleString()} <span class="arr">↑</span>{e.sent.toLocaleString()}{:else}no sync{/if}
        </span>
      </div>
    {/each}
  {/if}

  <div class="section-label">collected notes</div>
  {#if notes.length === 0}
    <div class="kv-row sub"><span class="dim">no notes from them here yet</span></div>
  {/if}
  {#each notes as note (note.id)}
    <NoteRow {store} {note} />
  {/each}
</div>
