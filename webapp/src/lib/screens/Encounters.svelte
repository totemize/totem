<script lang="ts">
  import FriendRow from "$lib/components/FriendRow.svelte";
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
</script>

<div class="screen">
  <button class="back section-back" onclick={() => store.show("peers")}><span class="arr">←</span> recently encountered</button>
  {#each store.state.encounterLog as entry, i (i)}
    <FriendRow {store} info={entry.peer} hint={relativeTime(entry.at)} />
  {/each}
</div>
