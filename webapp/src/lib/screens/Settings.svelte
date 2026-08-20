<script lang="ts">
  import { fullNpub, gigabytes, shortNpub } from "$lib/format";
  import type { Store } from "$lib/store.svelte";
  import { RETENTION_OPTIONS } from "$lib/types";

  const { store }: { store: Store } = $props();
  const node = $derived(store.state.node);
  const status = $derived(store.state.status);
  const settings = $derived(store.state.settings);

  let copied = $state<string | null>(null);
  function copy(key: string, value: string) {
    void navigator.clipboard.writeText(value);
    copied = key;
    setTimeout(() => (copied = null), 900);
  }

  let confirmingReset = $state(false);

  function danger(action: "wipe" | "rotate" | "reset") {
    if (action === "reset") {
      if (confirmingReset) {
        confirmingReset = false;
        void store.resetConfig();
      } else {
        confirmingReset = true;
      }
      return;
    }
    alert(
      action === "wipe"
        ? "Wipe flow — TBD (confirm + NIP-98 signed request)"
        : "Key rotation flow — TBD (confirm + NIP-98 signed request)",
    );
  }
</script>

<div class="screen">
  <div class="identity-row">
    <button class="chip copyable" title="copy" onclick={() => node && copy("npub", fullNpub(node.pubkey))}>
      {copied === "npub" ? "copied" : node ? shortNpub(node.pubkey) : ""}
    </button>
    <span class="at">at</span>
    <button class="chip copyable" title="copy" onclick={() => node && copy("relay", node.relayUrl)}>
      {copied === "relay" ? "copied" : (node?.relayUrl ?? "")}
    </button>
  </div>

  <div class="kv-row"><span>storage</span>
    <span class="storage-right">
      <span class="value">{status ? `${gigabytes(status.storageUsedBytes)} / ${gigabytes(status.storageTotalBytes)} GB` : ""}</span>
      <span class="retention-options">
        {#each RETENTION_OPTIONS as r (r)}
          <button class="retention-option" class:on={settings?.retention === r} onclick={() => store.updateSettings({ retention: r })}>{r}</button>
        {/each}
      </span>
    </span></div>

  <div class="kv-row"><span>make totem public</span>
    <button class="toggle" class:off={!settings?.publicTotem} onclick={() => store.updateSettings({ publicTotem: !settings?.publicTotem })} aria-label="make totem public"></button></div>
  {#if settings?.publicTotem}
    <div class="kv-row sub"><span>enable wifi for guests</span>
      <button class="toggle" class:off={!settings.wifiForGuests} onclick={() => store.updateSettings({ wifiForGuests: !settings?.wifiForGuests })} aria-label="enable wifi for guests"></button></div>
    <div class="kv-row sub"><span>allow guest notes</span>
      <button class="toggle" class:off={!settings.guestPosting} onclick={() => store.updateSettings({ guestPosting: !settings?.guestPosting })} aria-label="allow guest notes"></button></div>
  {/if}

  <details class="advanced">
    <summary>advanced</summary>
    <button class="danger-item" onclick={() => danger("wipe")}>wipe stored notes</button>
    <button class="danger-item" onclick={() => danger("rotate")}>rotate device key</button>
    <button class="danger-item" onclick={() => danger("reset")}>{confirmingReset ? "click again to confirm reset" : "reset config"}</button>
  </details>
</div>
