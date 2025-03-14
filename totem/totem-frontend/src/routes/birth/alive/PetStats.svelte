<script>
  export let petName = "PET NAME";
  
  // Stats with percentage values
  export let stats = {
    health: 100,
    happiness: 100,
    hunger: 10,
    thirst: 20,
    energy: 100,
    discipline: 100
  };
  
  // Colors for different stat bars
  const colors = {
    health: "bg-red-500",
    happiness: "bg-yellow-500",
    hunger: "bg-orange-500",
    thirst: "bg-blue-500", 
    energy: "bg-green-500",
    discipline: "bg-purple-500"
  };
</script>

<div class="w-full max-w-xs">
  <!-- Pet name -->
  <h2 class="mb-4 text-center text-lg font-medium uppercase tracking-wider">{petName}</h2>
  
  <!-- Stats with colored bars -->
  <div class="space-y-2">
    {#each Object.entries(stats) as [name, value]}
      <div class="flex items-center">
        <div class="w-24 text-xs uppercase">{name}:</div>
        <div class="relative h-3 flex-1 rounded-full bg-gray-200">
          <div 
            class="absolute left-0 top-0 h-3 rounded-full {colors[name]}" 
            style="width: {value}%;"
          ></div>
        </div>
        <div class="ml-2 w-10 text-right text-xs">{value}%</div>
      </div>
    {/each}
  </div>
</div> 