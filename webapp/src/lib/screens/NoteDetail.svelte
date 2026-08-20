<script lang="ts">
  import NoteRow from "$lib/components/NoteRow.svelte";
  import { relativeTime } from "$lib/format";
  import type { Store } from "$lib/store.svelte";

  const { store }: { store: Store } = $props();
  const note = $derived(store.state.openNote);
  const author = $derived(note?.own ? "you" : (note?.author?.name ?? "guest"));
  let draft = $state("");

  function reply() {
    const content = draft.trim();
    if (!content) return;
    void store.publishReply(content);
    draft = "";
  }
</script>

<div class="screen">
  <button class="back" onclick={() => store.closeNoteDetail()} ><span class="arr">←</span> back</button>
  {#if note}
    <div class="note" style="border-bottom:none; padding-top:4px">
      <div class="avatar"></div>
      <div class="body">
        <div class="meta">{author} · {relativeTime(note.at)}</div>
        <div class="content" style="font-size:14px">{note.content}</div>
      </div>
    </div>

    <div class="section-label">replies</div>
    {#if store.state.replies.length === 0}
      <div class="kv-row sub"><span class="dim">no replies yet</span></div>
    {/if}
    {#each store.state.replies as r (r.id)}
      <NoteRow {store} note={r} />
    {/each}

    <div class="composer" style="border-bottom:none">
      <textarea class="composer-input" rows="2" placeholder="leave a reply…" bind:value={draft}></textarea>
      <div class="composer-row">
        <button class="btn primary" onclick={reply}>reply</button>
      </div>
    </div>
  {/if}
</div>
