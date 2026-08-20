<script lang="ts">
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";
  import type { Note } from "$lib/types";

  const { store, note }: { store: Store; note: Note } = $props();
  const author = $derived(note.own ? "you" : (note.author?.name ?? "guest"));
  const menuOpen = $derived(store.state.noteMenu === note.id);
</script>

<div class="note">
  <div class="avatar"></div>
  <div class="body">
    <div class="meta">{author} · {relativeTime(note.at)}</div>
    <div class="content">{note.content}</div>
    {#if menuOpen}
      <div class="note-actions">
        <button class="btn danger" onclick={() => store.removeNote(note.id)}>remove from relay</button>
        <button class="btn" onclick={() => store.toggleNoteMenu(note.id)}>cancel</button>
      </div>
    {/if}
  </div>
  <button class="more" title="note actions" onclick={() => store.toggleNoteMenu(note.id)}>⋯</button>
</div>
