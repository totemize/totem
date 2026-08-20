<script lang="ts">
  import NoteRow from "$lib/components/NoteRow.svelte";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const filter = $derived(store.state.noteFilter);
  let draft = $state("");

  function post() {
    const content = draft.trim();
    if (!content) return;
    void store.publishNote(content);
    draft = "";
  }
</script>

<div class="screen">
  {#if store.state.composing}
    <div class="section-label center" style="padding-top:26px">create new note</div>
    <div class="composer" style="border-bottom:none">
      <!-- svelte-ignore a11y_autofocus -->
      <textarea class="composer-input" rows="3" placeholder="leave a note…" bind:value={draft} autofocus></textarea>
      <div class="composer-row">
        <button class="btn" onclick={() => store.setComposing(false)}>cancel</button>
        <button class="btn primary" onclick={post}>post</button>
      </div>
    </div>
  {:else}
    <div class="note-filters">
      <button class:on={filter === "all"} onclick={() => store.setNoteFilter("all")}>All notes</button>
      <button class:on={filter === "own"} onclick={() => store.setNoteFilter("own")}>Your notes</button>
      <button class="search">Search</button>
    </div>
    {#each store.state.notes as note (note.id)}
      <NoteRow {store} {note} />
    {/each}
    <div class="tiny center" style="padding:14px 20px">
      {#if store.state.status}{store.state.status.relayEventCount.toLocaleString()} notes collected{/if}
    </div>
    <div class="screen-plus">
      <div></div><div></div>
      <div class="center"><button class="plus" onclick={() => store.setComposing(true)}>+</button></div>
    </div>
  {/if}
</div>
