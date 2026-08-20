<script lang="ts">
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";
  import type { EncounterLogEntry } from "$lib/types";

  const { store, entry }: { store: Store; entry: EncounterLogEntry } = $props();
</script>

<div class="kv-row sub clickable" onclick={() => store.openPeer(entry.peer.pubkey)} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && store.openPeer(entry.peer.pubkey)}>
  <span>{entry.peer.name}</span>
  <span class="value">
    {relativeTime(entry.at)} · {entry.transport} ·
    {#if entry.verdict === "failed"}challenge failed{:else if entry.received || entry.sent}<span class="arr">↓</span>{entry.received.toLocaleString()} <span class="arr">↑</span>{entry.sent.toLocaleString()}{:else}no sync{/if}
  </span>
</div>
