<script lang="ts">
  import { createEgg, namePet } from '$lib/services/nostr';
	import { onMount } from 'svelte';
	import { writable } from 'svelte/store';

  // For e-screen (mobile screen) display
  let isMobile = false;

  const ready = writable(false);
  
  onMount(async () => {
    await createEgg();
    ready.set(true);
  })

  function handleSubmit(event: Event) {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const input = form.querySelector('input[type="text"]');
    if (input instanceof HTMLInputElement) {
      namePet(input.value);
    }
  }

</script>

<form on:submit={handleSubmit}>

<div class="flex flex-col items-center justify-center text-center">
  <!-- Egg image -->
  <img 
    src="/egg.svg" 
    alt="Pet Egg" 
    class="mb-6 h-auto w-24 md:w-32"
  />
  
  <!-- NAME ME text -->
  <h2 class="mb-4 text-lg font-normal tracking-wider md:text-xl">NAME ME</h2>
  
  <!-- Input field -->
  <input
    type="text"
    class="w-48 mb-3 max-w-full rounded bg-gray-200 px-4 py-2 text-center md:w-56"
    placeholder="Enter name..."
    
  />

  <input 
    type="submit"
    value="submit"
    class="w-48 max-w-full rounded bg-gray-200 px-4 py-2 text-center md:w-56"
  />
</div>

</form>

<!-- E-screen version (mobile QR version) -->
{#if isMobile}
<div class="fixed inset-0 flex flex-col items-center justify-center bg-white">
  <div class="mb-8 flex h-36 w-36 items-center justify-center bg-gray-200">
    <span class="text-2xl">QR</span>
  </div>
  <p class="text-center text-xs uppercase tracking-wide">
    USE THE WEB IN<br />YOUR DEVICE
  </p>
</div>
{/if}


