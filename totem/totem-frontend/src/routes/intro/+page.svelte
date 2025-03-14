<script>
  import AboutPage from './AboutPage.svelte';
  
  // State for showing the about page
  let showAbout = false;
</script>

<div class="flex items-center justify-center">
  <div class="flex flex-col items-center justify-center text-center">
    <!-- Character with question mark -->
    <div class="relative mb-6">
      <img 
        src="/orangutan.svg" 
        alt="Orangutan character" 
        class="h-auto w-40 md:w-48"
      />
      <span class="absolute right-0 top-0 text-4xl font-bold text-red-600 md:text-5xl">?</span>
    </div>
    
    <!-- WHO ARE YOU text -->
    <h2 class="mb-6 text-lg font-normal tracking-wider md:text-xl">WHO ARE YOU?</h2>
    
    <!-- Input field -->
    <input
      type="text"
      class="mb-4 w-48 max-w-full rounded bg-gray-200 px-4 py-2 text-center md:w-56"
      placeholder="Enter your name..."
    />
    
    <!-- Buttons -->
    <button class="mb-2 w-48 max-w-full rounded bg-gray-200 px-4 py-2 text-center text-sm uppercase md:w-56">
      Continue
    </button>
    
    <button 
      class="w-48 max-w-full rounded border border-gray-300 bg-gray-100 px-4 py-1 text-center text-xs uppercase md:w-56"
      on:click={() => showAbout = true}
    >
      How to play
    </button>
  </div>
  
  <!-- Right side text for desktop view -->
  <div class="ml-8 hidden md:block">
    <div class="flex flex-col items-center">
      <div class="relative">
        <img 
          src="/orangutan.svg" 
          alt="Orangutan character" 
          class="h-auto w-40"
        />
        <span class="absolute right-0 top-0 text-4xl font-bold text-red-600">?</span>
      </div>
      <div class="mt-2 text-center">
        <p class="mb-1 font-bold uppercase tracking-wider">I AM TOTEM,</p>
        <p class="font-bold uppercase tracking-wider">WHO ARE YOU?</p>
      </div>
    </div>
  </div>
</div>

<!-- About page component -->
<AboutPage bind:visible={showAbout} />
