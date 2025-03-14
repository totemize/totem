<script>
  // For e-screen (mobile screen) display
  let isMobile = false;
  
  // Death info - in a real app, this would come from a store or props
  const deathInfo = {
    blocksAgo: 2
  };
</script>

<div class="flex flex-col items-center justify-center text-center">
  <!-- Character with skull -->
  <div class="relative mb-6">
    <img 
      src="/orangutan.svg" 
      alt="Orangutan character" 
      class="h-auto w-40 md:w-48"
    />
    <img
      src="/skull.svg"
      alt="Skull"
      class="absolute left-1/2 top-0 h-auto w-28 -translate-x-1/2 transform md:w-32"
    />
  </div>
  
  <!-- Death message -->
  <h2 class="text-lg font-normal uppercase tracking-wider md:text-xl">
    DIED {deathInfo.blocksAgo} BLOCKS AGO
  </h2>
</div>

<!-- E-screen version (mobile QR version) -->
{#if isMobile}
<div class="fixed inset-0 flex flex-col items-center justify-center bg-white">
  <div class="relative mb-8">
    <img 
      src="/orangutan.svg" 
      alt="Orangutan character" 
      class="h-auto w-40"
    />
    <img
      src="/skull.svg"
      alt="Skull"
      class="absolute left-1/2 top-0 h-auto w-28 -translate-x-1/2 transform"
    />
  </div>
  <p class="text-center text-sm uppercase tracking-wider">
    DIED {deathInfo.blocksAgo}<br />BLOCKS AGO
  </p>
</div>
{/if} 