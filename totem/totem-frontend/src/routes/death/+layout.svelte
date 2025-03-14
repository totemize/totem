<script>
  // Detect if we should show mobile version
  import { onMount } from 'svelte';
  
  let isMobile = false;
  let windowWidth = 0;
  
  // Handle screen resize to detect mobile
  function handleResize() {
    windowWidth = window.innerWidth;
    isMobile = windowWidth < 768; // If less than 768px, consider as mobile
  }
  
  onMount(() => {
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  });
</script>

<!-- Mobile e-screen QR display -->
{#if isMobile}
  <div class="fixed inset-0 flex flex-col items-center justify-center bg-white p-4">
    <div class="relative mb-8">
      <img 
        src="/orangutan.svg" 
        alt="Orangutan character" 
        class="h-auto w-32"
      />
      <img
        src="/skull.svg"
        alt="Skull"
        class="absolute left-1/2 top-0 h-auto w-24 -translate-x-1/2 transform"
      />
    </div>
    <p class="text-center text-xs uppercase tracking-wide">
      DIED 2<br />BLOCKS AGO
    </p>
  </div>
{:else}
  <!-- Regular content for non-mobile -->
  <div class="flex min-h-screen w-full items-center justify-center bg-white p-4">
    <slot />
  </div>
{/if}
