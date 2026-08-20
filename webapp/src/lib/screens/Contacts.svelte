<script lang="ts">
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const filter = $derived(store.state.contactFilter);
  const shown = $derived(
    store.state.peers.filter(
      (p) => p.relation.kind !== "request" && (filter === "all" || p.relation.kind === "friend"),
    ),
  );
</script>

<div class="screen">
  <button class="back" onclick={() => store.show("peers")}>‹ Friends</button>
  <div class="note-filters" style="padding-top:6px">
    <button class:on={filter === "all"} onclick={() => store.setContactFilter("all")}>All friends</button>
    <button class="search">Search</button>
  </div>
  {#each shown as peer (peer.info.pubkey)}
    <div class="item clickable" onclick={() => store.openPeer(peer.info.pubkey)} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && store.openPeer(peer.info.pubkey)}>
      <div class="avatar"></div>
      <span class="label">{peer.info.name}</span>
      <span class="hint">{peer.lastMet ? `met ${relativeTime(peer.lastMet)}` : ""}</span>
      <span class="chev">›</span>
    </div>
  {/each}
</div>
