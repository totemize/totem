<script lang="ts">
  import type { Screen, Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const tabs: { screen: Screen; label: string }[] = [
    { screen: "peers", label: "Peers" },
    { screen: "home", label: "Home" },
    { screen: "notes", label: "Notes" },
  ];
</script>

<nav class="tabbar">
  {#each tabs as tab (tab.screen)}
    <button class:on={store.state.screen === tab.screen} onclick={() => store.show(tab.screen)}>
      {tab.label}
    </button>
  {/each}
</nav>
