<script lang="ts">
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const node = $derived(store.state.node);

  const activity = $derived(store.activity().slice(0, 3));

  function open(event: ReturnType<Store["activity"]>[number]) {
    if (event.note) void store.openNoteDetail(event.note);
    else if (event.peer) store.openLanding(event.peer);
  }
</script>

<div class="screen">
  <div class="home-hero center clickable-plain" onclick={() => node && store.openLanding(node)} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && node && store.openLanding(node)}>
    {#if node?.picture}
      <img class="mark mark-img" src={node.picture} alt="">
    {:else}
      <div class="mark">T</div>
    {/if}
    <h1>{node?.name ?? "…"}</h1>
  </div>
  <div class="activity center">
    <div class="activity-title dim">recent activity</div>
    {#each activity as event, i (i)}
      <button class="tiny activity-item" onclick={() => open(event)}>{event.text}, ~{relativeTime(event.at).replace(/\s+/g, "")}</button>
    {/each}
    <button class="see-all" style="align-self:center; padding:10px 0 0" onclick={() => store.show("activity")}>view all ›</button>
  </div>
  <div class="pets center dim">no pets yet, soon™</div>
  <div class="quick-row">
    <div class="center"><button class="plus" onclick={() => { store.show("peers"); alert("New connection flow — TBD (QR / nearby discovery)"); }}>+</button></div>
    <div></div>
    <div class="center"><button class="plus" onclick={() => store.setComposing(true)}>+</button></div>
  </div>
</div>
