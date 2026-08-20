<script lang="ts">
  import EncounterRow from "$lib/components/EncounterRow.svelte";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
</script>

<div class="screen">
  <button class="back" onclick={() => store.show("peers")}>‹ Friends</button>
  <div class="section-label" style="padding-top:4px">all encounters</div>
  {#each store.state.encounterLog as entry, i (i)}
    <EncounterRow {store} {entry} />
  {/each}
</div>
