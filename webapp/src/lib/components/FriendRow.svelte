<script lang="ts">
  import type { Store } from "$lib/store.svelte";
  import type { NodeInfo } from "$lib/types";

  const { store, info, hint = "" }: { store: Store; info: NodeInfo; hint?: string } = $props();
</script>

<div class="item clickable" onclick={() => store.openLanding(info)} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && store.openLanding(info)}>
  <div class="avatar"></div>
  <span class="label">{info.name}</span>
  <span class="hint">{hint}</span>
  <span class="chev">›</span>
</div>
