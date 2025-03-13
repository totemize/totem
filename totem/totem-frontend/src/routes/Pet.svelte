<!-- Pet.svelte -->
<script>
	export let pet;

	function formatTime(timeString) {
		if (!timeString) return 'Never';
		// Try to handle the time string format from the example
		try {
			return new Date(timeString).toLocaleTimeString();
		} catch (e) {
			return timeString;
		}
	}
</script>

<div
	class={`rounded-xl border-2 p-6 text-center transition-all hover:translate-y-[-5px] hover:shadow-md ${pet.stateEmoji === '🥚' ? 'border-amber-200 bg-amber-50' : 'border-gray-200'}`}
>
	<div class="my-2 text-5xl">{pet.stateEmoji}</div>
	<div class="mt-4 text-left">
		<h3 class="text-xl font-bold">{pet.name || 'Unnamed Egg'}</h3>
		<p class="my-1"><strong>Nostr ID:</strong> <code class="text-xs">{pet.pubkey}</code></p>

		{#if pet.about}
			<p class="my-1"><strong>About:</strong> {pet.about}</p>
		{/if}

		<p class="my-1"><strong>Energy:</strong> {pet.energy?.toFixed(1)}%</p>
		<div class="h-2 overflow-hidden rounded bg-gray-200">
			<div class="h-full rounded bg-green-500" style="width: {pet.energy}%;"></div>
		</div>

		<p class="my-1"><strong>Happiness:</strong> {pet.happiness?.toFixed(1)}%</p>
		<div class="h-2 overflow-hidden rounded bg-gray-200">
			<div class="h-full rounded bg-blue-500" style="width: {pet.happiness}%;"></div>
		</div>

		<p class="my-1"><strong>Last Fed:</strong> {formatTime(pet.lastFed)}</p>

		{#if pet.stateEmoji === '🥚'}
			<p class="mt-2 italic">This pet is still an egg! Send a naming event to hatch it.</p>
		{/if}

		<p class="mt-2 text-xs text-gray-500">Last updated: {pet.lastUpdated?.toLocaleString()}</p>
	</div>
</div>
