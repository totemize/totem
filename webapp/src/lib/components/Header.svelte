<script lang="ts">
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const status = $derived(store.state.status);
  const inSettings = $derived(store.state.screen === "settings");
</script>

<div class="header" onclick={() => store.toggleSettings()} role="button" tabindex="0" onkeydown={(e) => e.key === "Enter" && store.toggleSettings()}>
  <span class="wordmark">totem</span>
  {#if status}
    <span class="status-line">
      <div>{status.health === "good" ? "All good" : status.health} <span class="dot">●</span> {status.batteryPct}%</div>
      {#if inSettings}<div class="battery-left">~{status.batteryHoursLeft}h</div>{/if}
    </span>
  {/if}
</div>
