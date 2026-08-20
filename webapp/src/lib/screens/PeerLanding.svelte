<script lang="ts">
  import NoteRow from "$lib/components/NoteRow.svelte";
  import { shortNpub } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const peer = $derived(store.state.peers.find((p) => p.info.pubkey === store.state.selectedPeer));
  const theirNotes = $derived(store.state.notes.filter((n) => n.author?.pubkey === store.state.selectedPeer));
</script>

<div class="screen">
  <button class="back" onclick={() => store.closePeer()}>‹ Friends</button>
  <div class="pad center" style="padding:24px">
    <div class="mark">T</div>
    <h1 style="font-size:18px">{peer?.info.name ?? "unknown"}</h1>
    <div class="tiny" style="margin-top:8px">{peer ? shortNpub(peer.info.pubkey) : ""} · {peer?.info.relayUrl ?? ""}</div>
  </div>
  <div class="section-label">collected notes</div>
  {#if theirNotes.length === 0}
    <div class="kv-row sub"><span class="dim">no notes from them here yet</span></div>
  {/if}
  {#each theirNotes as note (note.id)}
    <NoteRow {store} {note} />
  {/each}
</div>
