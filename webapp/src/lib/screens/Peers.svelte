<script lang="ts">
  import EncounterRow from "$lib/components/EncounterRow.svelte";
  import RequestRow from "$lib/components/RequestRow.svelte";
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const peers = $derived(store.state.peers);
  const filter = $derived(store.state.friendFilter);
  const active = $derived(peers.filter((p) => p.connected));
  const requests = $derived(peers.filter((p) => p.relation.kind === "request"));
  const friends = $derived(peers.filter((p) => p.relation.kind !== "request"));
  const recent = $derived(store.state.encounterLog.slice(0, 5));
</script>

<div class="screen">
  <div class="note-filters">
    <button class:on={filter === "all"} onclick={() => store.setFriendFilter("all")}>All friends ({friends.length})</button>
    <button class:on={filter === "active"} onclick={() => store.setFriendFilter("active")}>Active friends ({active.length})</button>
    <button class:on={filter === "requests"} onclick={() => store.setFriendFilter("requests")}>Requests ({requests.length})</button>
    <button class="search">Search</button>
  </div>

  {#if filter === "all"}
    {#each friends as peer (peer.info.pubkey)}
      <div class="item clickable" onclick={() => store.openPeer(peer.info.pubkey)} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && store.openPeer(peer.info.pubkey)}>
        <div class="avatar"></div>
        <span class="label">{peer.info.name}</span>
        <span class="hint">{peer.lastMet ? `met ${relativeTime(peer.lastMet)}` : ""}</span>
        <span class="chev">›</span>
      </div>
    {/each}
  {:else if filter === "active"}
    {#if active.length === 0}
      <div class="kv-row sub"><span class="dim">no one connected right now</span></div>
    {/if}
    {#each active as peer (peer.info.pubkey)}
      <div class="kv-row sub clickable" onclick={() => store.openPeer(peer.info.pubkey)} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && store.openPeer(peer.info.pubkey)}>
        <span>{peer.info.name}</span>
        <span class="value">{peer.connected?.transport}</span>
      </div>
    {/each}

    <div class="section-label">recently connected</div>
    {#each recent as entry, i (i)}
      <EncounterRow {store} {entry} />
    {/each}
    <button class="see-all" onclick={() => store.show("encounters")}>view all ›</button>
  {:else}
    {#if requests.length === 0}
      <div class="kv-row sub"><span class="dim">no pending requests</span></div>
    {/if}
    {#each requests as peer (peer.info.pubkey)}
      <RequestRow {store} {peer} />
    {/each}
  {/if}

  <div class="screen-plus">
    <div class="center"><button class="plus" onclick={() => alert("New connection flow — TBD (QR / nearby discovery)")}>+</button></div>
    <div></div><div></div>
  </div>
</div>
