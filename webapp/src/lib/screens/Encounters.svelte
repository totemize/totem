<script lang="ts">
  import FriendRow from "$lib/components/FriendRow.svelte";
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
</script>

<div class="screen">
  <button class="back" onclick={() => store.show("peers")}><span class="arr">←</span> Friends</button>
  <div class="section-label" style="padding-top:4px">all encounters</div>
  {#each store.state.encounterLog as entry, i (i)}
    <FriendRow {store} info={entry.peer} hint={relativeTime(entry.at)} />
  {/each}
</div>
