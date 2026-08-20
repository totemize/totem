<script lang="ts">
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const node = $derived(store.state.node);
  const enc = $derived(store.state.status?.lastEncounter ?? null);
</script>

<div class="screen">
  <div class="home-hero center clickable-plain" onclick={() => node && store.openLanding(node)} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && node && store.openLanding(node)}>
    <div class="mark">T</div>
    <h1>{node?.name ?? "…"}</h1>
    {#if enc}
      <span class="tiny last-met">last met {enc.peer.name}, {relativeTime(enc.at)} ago</span>
    {/if}
  </div>
  <div class="pets center dim">no pets yet, soon™</div>
  <div class="quick-row">
    <div class="center"><button class="plus" onclick={() => { store.show("peers"); alert("New connection flow — TBD (QR / nearby discovery)"); }}>+</button></div>
    <div></div>
    <div class="center"><button class="plus" onclick={() => store.setComposing(true)}>+</button></div>
  </div>
</div>
