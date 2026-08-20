<script lang="ts">
  import Header from "$lib/components/Header.svelte";
  import TabBar from "$lib/components/TabBar.svelte";
  import { MockBus, MockRelay } from "$lib/mock";
  import Encounters from "$lib/screens/Encounters.svelte";
  import Home from "$lib/screens/Home.svelte";
  import Notes from "$lib/screens/Notes.svelte";
  import Landing from "$lib/screens/Landing.svelte";
  import Peers from "$lib/screens/Peers.svelte";
  import Settings from "$lib/screens/Settings.svelte";
  import Setup from "$lib/screens/Setup.svelte";
  import { Store } from "$lib/store.svelte";

  // Swap MockBus/MockRelay for real clients (totemd web port + relay ws) later.
  const store = new Store(new MockBus(), new MockRelay());
  void store.refresh();

  const screen = $derived(store.state.screen);
</script>

<div class="app">
  {#if store.state.setup}
    <Setup {store} />
  {:else}
    <Header {store} />
    {#if screen === "home"}<Home {store} />
    {:else if screen === "peers"}<Peers {store} />
    {:else if screen === "notes"}<Notes {store} />
    {:else if screen === "encounters"}<Encounters {store} />
    {:else if screen === "landing"}<Landing {store} />
    {:else}<Settings {store} />{/if}
    <TabBar {store} />
  {/if}
</div>
