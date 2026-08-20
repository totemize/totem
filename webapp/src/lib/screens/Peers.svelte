<script lang="ts">
  import EncounterRow from "$lib/components/EncounterRow.svelte";
  import RequestRow from "$lib/components/RequestRow.svelte";
  import { shortNpub } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const node = $derived(store.state.node);
  const peers = $derived(store.state.peers);
  const active = $derived(peers.filter((p) => p.connected));
  const requests = $derived(peers.filter((p) => p.relation.kind === "request"));
  const recent = $derived(store.state.encounterLog.slice(0, 5));
</script>

<div class="screen">
  <div class="self-card">
    <div class="mark">T</div>
    <div>
      <div class="name">{node?.name ?? "…"}</div>
      <div class="tiny">{node ? shortNpub(node.pubkey) : ""}</div>
    </div>
    <button class="peer-count" onclick={() => store.show("contacts")}>{active.length} / {peers.length} friends ›</button>
  </div>

  {#if requests.length}
    <div class="section-label">requests</div>
    {#each requests as peer (peer.info.pubkey)}
      <RequestRow {store} {peer} />
    {/each}
  {/if}

  <div class="section-label">active connections</div>
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

  <div class="screen-plus">
    <div class="center"><button class="plus" onclick={() => alert("New connection flow — TBD (QR / nearby discovery)")}>+</button></div>
    <div></div><div></div>
  </div>
</div>
