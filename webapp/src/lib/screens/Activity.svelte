<script lang="ts">
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const events = $derived(store.activity());

  function open(event: ReturnType<Store["activity"]>[number]) {
    if (event.note) void store.openNoteDetail(event.note);
    else if (event.peer) store.openLanding(event.peer);
  }
</script>

<div class="screen">
  <button class="back" onclick={() => store.show("home")}><span class="arr">←</span> recent activity</button>
  <div class="activity center" style="padding-top:10px">
    {#each events as event, i (i)}
      <button class="tiny activity-item" onclick={() => open(event)}>{event.text}, ~{relativeTime(event.at).replace(/\s+/g, "")}</button>
    {/each}
  </div>
</div>
