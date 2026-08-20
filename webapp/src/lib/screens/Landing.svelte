<script lang="ts">
  import NoteRow from "$lib/components/NoteRow.svelte";
  import { relativeTime, shortNpub } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const info = $derived(store.state.landing);
  const peer = $derived(store.state.peers.find((p) => p.info.pubkey === info?.pubkey));
  const notes = $derived(store.state.notes.filter((n) => n.author?.pubkey === info?.pubkey));
  const encounters = $derived(store.state.encounterLog.filter((e) => e.peer.pubkey === info?.pubkey));
  const isSelf = $derived(info?.pubkey === store.state.node?.pubkey);
  let editing = $state(false);
  let editName = $state("");
  let editPicture = $state("");

  function startEdit() {
    editName = info?.name ?? "";
    editPicture = info?.picture ?? "";
    editing = true;
  }

  async function saveEdit() {
    await store.editProfile(editName, editPicture);
    editing = false;
  }
</script>

<div class="screen">
  <div class="subview-bar">
    <button class="back" onclick={() => store.closeLanding()}><span class="arr">←</span> back</button>
    {#if isSelf}
      {#if editing}
        <button class="edit-link" onclick={() => (editing = false)}>cancel</button>
      {:else}
        <button class="edit-link" onclick={startEdit}>edit</button>
      {/if}
    {/if}
  </div>
  <div class="pad center" style="padding:24px">
    {#if editing}
      <div class="edit-field">
        <span class="edit-label">name</span>
        <input class="name-input" type="text" bind:value={editName} spellcheck="false"
          onkeydown={(e) => e.key === "Enter" && saveEdit()}>
      </div>
      <div class="edit-field">
        <span class="edit-label">picture</span>
        <div class="picture-row">
          {#if editPicture}
            <img class="mark mark-img edit-mark" src={editPicture} alt="">
          {:else}
            <div class="mark edit-mark">T</div>
          {/if}
          <input class="name-input" type="text" bind:value={editPicture} placeholder="picture url…"
            spellcheck="false" autocapitalize="off" autocomplete="off"
            onkeydown={(e) => e.key === "Enter" && saveEdit()}>
        </div>
      </div>
      <div class="save-row">
        <button class="btn primary" onclick={saveEdit}>save</button>
      </div>
    {:else}
      {#if info?.picture}
        <img class="mark mark-img" src={info.picture} alt="">
      {:else}
        <div class="mark">T</div>
      {/if}
      <h1 style="font-size:18px">{info?.name ?? "unknown"}</h1>
    {/if}
    <div class="tiny" style="margin-top:8px">{info ? shortNpub(info.pubkey) : ""} · {info?.relayUrl ?? ""}</div>
    {#if peer?.connected}
      <div class="tiny" style="margin-top:4px">connected · {peer.connected.transport}</div>
    {/if}
  </div>

  {#if encounters.length}
    <div class="section-label">encounters</div>
    {#each encounters as e, i (i)}
      <div class="kv-row sub">
        <span>{relativeTime(e.at)}</span>
        <span class="value">{e.transport} ·
          {#if e.verdict === "failed"}challenge failed{:else if e.received || e.sent}<span class="arr">↓</span>{e.received.toLocaleString()} <span class="arr">↑</span>{e.sent.toLocaleString()}{:else}no sync{/if}
        </span>
      </div>
    {/each}
  {/if}

  <div class="section-label">collected notes</div>
  {#if notes.length === 0}
    <div class="kv-row sub"><span class="dim">no notes from them here yet</span></div>
  {/if}
  {#each notes as note (note.id)}
    <NoteRow {store} {note} />
  {/each}
</div>
