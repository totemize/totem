<script lang="ts">
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const setup = $derived(store.state.setup!);
  let name = $state("");

  $effect(() => {
    if (setup.step === "name") name = store.state.node?.name ?? "";
  });
</script>

{#if setup.step === "welcome"}
  <div class="screen setup center">
    <div class="mark">T</div>
    <h1>{store.state.node?.name ?? "totem"}</h1>
    <div class="claim-group">
      <p class="dim">This totem has no owner yet.</p>
      <button class="btn primary" onclick={() => store.setupGo("identity")}>claim this totem</button>
    </div>
  </div>
{:else if setup.step === "identity"}
  <div class="screen setup center">
    <h1>Claim this totem with</h1>
    <div class="connect-options">
      <button class="connect-option" onclick={() => store.setupConnect("bunker")}>
        <span class="connect-title">bunker</span>
      </button>
      <button class="connect-option" onclick={() => store.setupConnect("extension")}>
        <span class="connect-title">extension</span>
      </button>
    </div>
    {#if setup.error}<div class="setup-error">{setup.error}</div>{/if}
  </div>
{:else if setup.step === "presence"}
  <div class="screen setup center">
    <h1>Prove you're there</h1>
    <p class="dim">Press the button on the totem<br>(or tap it with your phone).</p>
    <div class="presence-pulse"></div>
    <p class="tiny">waiting for the device…</p>
  </div>
{:else if setup.step === "name"}
  <div class="screen setup center">
    <h1>Name your totem</h1>
    <input class="name-input" type="text" bind:value={name} spellcheck="false"
      onkeydown={(e) => e.key === "Enter" && store.setupSetName(name)}>
    <button class="btn primary" onclick={() => store.setupSetName(name)}>continue</button>
  </div>
{:else if setup.step === "public"}
  {@const settings = store.state.settings}
  <div class="screen setup center">
    <h1>Make it public?</h1>
    <p class="dim">Public totems meet other totems and welcome guests.<br>You can change this any time in settings.</p>
    <div class="setup-toggles">
      <div class="kv-row"><span>make totem public</span>
        <button class="toggle" class:off={!settings?.publicTotem} onclick={() => store.updateSettings({ publicTotem: !settings?.publicTotem })} aria-label="make totem public"></button></div>
      {#if settings?.publicTotem}
        <div class="kv-row sub"><span>enable wifi for guests</span>
          <button class="toggle" class:off={!settings.wifiForGuests} onclick={() => store.updateSettings({ wifiForGuests: !settings?.wifiForGuests })} aria-label="enable wifi for guests"></button></div>
        <div class="kv-row sub"><span>allow guest notes</span>
          <button class="toggle" class:off={!settings.guestPosting} onclick={() => store.updateSettings({ guestPosting: !settings?.guestPosting })} aria-label="allow guest notes"></button></div>
      {/if}
    </div>
    <button class="btn primary" onclick={() => store.setupFinish()}>done</button>
  </div>
{/if}
