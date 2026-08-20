<script lang="ts">
  import FriendRow from "$lib/components/FriendRow.svelte";
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
    <button class:on={filter === "all"} onclick={() => store.setFriendFilter("all")}>All friends</button>
    <button class:on={filter === "active"} onclick={() => store.setFriendFilter("active")}>Active</button>
    <button class:on={filter === "requests"} onclick={() => store.setFriendFilter("requests")}>Requests</button>
    <button class="search">Search</button>
  </div>

  {#if filter === "all"}
    {#each friends as peer (peer.info.pubkey)}
      <FriendRow {store} info={peer.info} hint={peer.lastMet ? `met ${relativeTime(peer.lastMet)}` : ""} />
    {/each}
  {:else if filter === "active"}
    {#if active.length === 0}
      <div class="kv-row sub"><span class="dim">no one connected right now</span></div>
    {/if}
    {#each active as peer (peer.info.pubkey)}
      <FriendRow {store} info={peer.info} hint="connected" />
    {/each}

    <div class="section-label">recently encountered</div>
    {#each recent as entry, i (i)}
      <FriendRow {store} info={entry.peer} hint={relativeTime(entry.at)} />
    {/each}
    <button class="see-all" onclick={() => store.show("encounters")}>view all ›</button>
  {:else}
    {#if requests.length === 0}
      <div class="kv-row sub"><span class="dim">no pending requests</span></div>
    {/if}
    {#each requests as peer (peer.info.pubkey)}
      <RequestRow {store} peer={peer} />
    {/each}
  {/if}

  <div class="screen-plus">
    <div class="center"><button class="plus" onclick={() => alert("New connection flow — TBD (QR / nearby discovery)")}>+</button></div>
    <div></div><div></div>
  </div>
</div>
