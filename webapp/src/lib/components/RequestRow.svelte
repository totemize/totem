<script lang="ts">
  import type { Store } from "$lib/store.svelte";
  import type { Peer } from "$lib/types";

  const { store, peer }: { store: Store; peer: Peer } = $props();
</script>

<div class="item clickable" onclick={() => store.openPeer(peer.info.pubkey)} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && store.openPeer(peer.info.pubkey)}>
  <div class="avatar"></div>
  <span class="label">{peer.info.name}</span>
  <span class="hint">wants to be friends</span>
  <button class="btn primary" onclick={(e) => { e.stopPropagation(); store.answerPeerRequest(peer.info.pubkey, true); }}>Yes</button>
  <button class="btn" onclick={(e) => { e.stopPropagation(); store.answerPeerRequest(peer.info.pubkey, false); }}>No</button>
</div>
