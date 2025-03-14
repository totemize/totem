<script>
  // For responsive sizing
  export let size = "large"; // "small" | "medium" | "large"
</script>

<div class="flex flex-col items-center">
  <div class="relative">
    <img 
      src="/orangutan.svg" 
      alt="Orangutan" 
      class="{size === 'small' ? 'w-24' : size === 'medium' ? 'w-32' : 'w-40'} h-auto"
    />
    <span 
      class="absolute right-0 top-0 text-red-600"
      class:text-3xl={size === 'small'}
      class:text-4xl={size === 'medium'}
      class:text-5xl={size === 'large'}
    >?</span>
  </div>
  
  <div class="mt-3 text-center">
    <h2 
      class="text-base font-medium uppercase tracking-wider"
      class:text-sm={size === 'small'}
      class:text-base={size === 'medium'}
      class:text-lg={size === 'large'}
    >
      ABOUT...
    </h2>
  </div>
</div> 