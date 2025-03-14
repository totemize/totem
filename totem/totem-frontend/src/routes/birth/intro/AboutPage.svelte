<script>
  // Props
  export let visible = false;
</script>

{#if visible}
<div class="fixed inset-0 flex items-center justify-center bg-white p-4">
  <div class="max-w-md rounded-lg bg-gray-100 p-6 shadow-lg">
    <div class="mb-4 flex items-center justify-between">
      <h2 class="text-xl font-bold">ABOUT...</h2>
      <button 
        class="rounded-full bg-gray-200 px-3 py-1 text-sm hover:bg-gray-300"
        on:click={() => visible = false}
      >
        Close
      </button>
    </div>
    
    <div class="mb-6 space-y-3 text-sm">
      <p>
        Totem is a virtual pet that lives on the Nostr network. Your pet needs care and attention to thrive.
      </p>
      <p>
        Each pet is unique and will develop based on how you interact with it. Feed it, play with it, and watch it grow!
      </p>
      <p>
        Your pet's status is stored on the blockchain, making it truly yours and accessible from anywhere.
      </p>
    </div>
    
    <div class="mt-6 flex justify-center">
      <button 
        class="rounded-md bg-gray-300 px-3 py-1 text-sm"
        on:click={() => visible = false}
      >
        GOT IT!
      </button>
    </div>
  </div>
</div>
{/if} 