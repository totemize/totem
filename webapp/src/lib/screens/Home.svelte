<script lang="ts">
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const node = $derived(store.state.node);

  /** Latest activity of all kinds, newest first. */
  const activity = $derived.by(() => {
    const events: { at: Date; text: string }[] = [];
    for (const e of store.state.encounterLog) {
      events.push({
        at: e.at,
        text: e.verdict === "failed" ? "a stranger failed the challenge" : `met ${e.peer.name}`,
      });
    }
    for (const n of store.state.notes) {
      events.push({
        at: n.at,
        text: n.own ? "you posted a note" : `${n.author?.name ?? "a guest"} left a note`,
      });
    }
    return events.sort((a, b) => b.at.getTime() - a.at.getTime()).slice(0, 5);
  });
</script>

<div class="screen">
  <div class="home-hero center clickable-plain" onclick={() => node && store.openLanding(node)} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && node && store.openLanding(node)}>
    <div class="mark">T</div>
    <h1>{node?.name ?? "…"}</h1>
  </div>
  <div class="activity center">
    <div class="activity-title">recent activity</div>
    {#each activity as event, i (i)}
      <div class="tiny">{event.text}, {relativeTime(event.at)} ago</div>
    {/each}
  </div>
  <div class="pets center dim">no pets yet, soon™</div>
  <div class="quick-row">
    <div class="center"><button class="plus" onclick={() => { store.show("peers"); alert("New connection flow — TBD (QR / nearby discovery)"); }}>+</button></div>
    <div></div>
    <div class="center"><button class="plus" onclick={() => store.setComposing(true)}>+</button></div>
  </div>
</div>
