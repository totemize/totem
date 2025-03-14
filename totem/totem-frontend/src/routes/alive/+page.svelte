<script>
  import PetStats from './PetStats.svelte';
  
  // For e-screen (mobile screen) display
  let isMobile = false;
  
  // Pet stats - in a real app, these would come from a store or props
  const petName = "TOTEM";
  const petStats = {
    health: 100,
    happiness: 96,
    hunger: 10,
    thirst: 21,
    energy: 100,
    discipline: 98
  };
</script>

<div class="flex flex-col items-center justify-center text-center">
  <!-- Character -->
  <img 
    src="/orangutan.svg" 
    alt="Orangutan character" 
    class="mb-4 h-auto w-40 md:w-48"
  />
  
  <!-- Pet stats using the component -->
  <PetStats petName={petName} stats={petStats} />
</div>

<!-- E-screen version (mobile QR version) -->
{#if isMobile}
<div class="fixed inset-0 flex flex-col items-center justify-center bg-white">
  <div class="mb-4">
    <img 
      src="/orangutan.png" 
      alt="Orangutan character" 
      class="h-auto w-32"
    />
  </div>
  <h3 class="mb-2 text-base uppercase">{petName}</h3>
  
  <!-- Simplified stats display for mobile -->
  <div class="flex gap-2">
    <div class="flex flex-col">
      <div class="h-3 w-3 rounded-full bg-red-500"></div>
      <div class="h-3 w-3 rounded-full bg-yellow-500"></div>
      <div class="h-3 w-3 rounded-full bg-orange-500"></div>
    </div>
    <div class="flex flex-col">
      <div class="h-3 w-20 rounded-full bg-gray-200">
        <div class="h-3 rounded-full bg-red-500" style="width: {petStats.health}%;"></div>
      </div>
      <div class="h-3 w-20 rounded-full bg-gray-200">
        <div class="h-3 rounded-full bg-yellow-500" style="width: {petStats.happiness}%;"></div>
      </div>
      <div class="h-3 w-20 rounded-full bg-gray-200">
        <div class="h-3 rounded-full bg-orange-500" style="width: {petStats.hunger}%;"></div>
      </div>
    </div>
    <div class="flex flex-col">
      <div class="h-3 w-3 rounded-full bg-blue-500"></div>
      <div class="h-3 w-3 rounded-full bg-green-500"></div>
      <div class="h-3 w-3 rounded-full bg-purple-500"></div>
    </div>
    <div class="flex flex-col">
      <div class="h-3 w-20 rounded-full bg-gray-200">
        <div class="h-3 rounded-full bg-blue-500" style="width: {petStats.thirst}%;"></div>
      </div>
      <div class="h-3 w-20 rounded-full bg-gray-200">
        <div class="h-3 rounded-full bg-green-500" style="width: {petStats.energy}%;"></div>
      </div>
      <div class="h-3 w-20 rounded-full bg-gray-200">
        <div class="h-3 rounded-full bg-purple-500" style="width: {petStats.discipline}%;"></div>
      </div>
    </div>
  </div>
</div>
{/if}
