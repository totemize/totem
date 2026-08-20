<script lang="ts">
  import NoteRow from "$lib/components/NoteRow.svelte";
  import { relativeTime, shortNpub } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const peer = $derived(store.state.peers.find((p) => p.info.pubkey === store.state.selectedPeer));
  const info = $derived(
    peer?.info ??
      (store.state.node?.pubkey === store.state.selectedPeer ? store.state.node : null),
  );
  const theirNotes = $derived(store.state.notes.filter((n) => n.author?.pubkey === store.state.selectedPeer));
  const theirEncounters = $derived(store.state.encounterLog.filter((e) => e.peer.pubkey === store.state.selectedPeer));
</script>

<div class="screen">
  <button class="back" onclick={() => store.closePeer()}><span class="arr">←</span> Friends</button>
  <div class="pad center" style="padding:24px">
    <div class="mark">T</div>
    <h1 style="font-size:18px">{info?.name ?? "unknown"}</h1>
    <div class="tiny" style="margin-top:8px">{info ? shortNpub(info.pubkey) : ""} · {info?.relayUrl ?? ""}</div>
    {#if peer?.connected}
      <div class="tiny" style="margin-top:4px">connected · {peer.connected.transport}</div>
    {/if}
  </div>

  {#if theirEncounters.length}
    <div class="section-label">encounters</div>
    {#each theirEncounters as e, i (i)}
      <div class="kv-row sub">
        <span>{relativeTime(e.at)}</span>
        <span class="value">{e.transport} ·
          {#if e.verdict === "failed"}challenge failed{:else if e.received || e.sent}<span class="arr">↓</span>{e.received.toLocaleString()} <span class="arr">↑</span>{e.sent.toLocaleString()}{:else}no sync{/if}
        </span>
      </div>
    {/each}
  {/if}

  <div class="section-label">collected notes</div>
  {#if theirNotes.length === 0}
    <div class="kv-row sub"><span class="dim">no notes from them here yet</span></div>
  {/if}
  {#each theirNotes as note (note.id)}
    <NoteRow {store} {note} />
  {/each}
</div>
