<script>
	export let pet;
	import { namePet } from '$lib/services/nostr';

	let nameInput = '';
	let isNaming = false;

	function formatTime(timeString) {
		if (!timeString) return 'Never';
		// Try to handle the time string format from the example
		try {
			return new Date(timeString).toLocaleTimeString();
		} catch (e) {
			return timeString;
		}
	}

	function startNaming() {
		isNaming = true;
		nameInput = '';
	}

	function submitName() {
		if (nameInput.trim()) {
			namePet(nameInput.trim(), pet.pubkey);
			isNaming = false;
		}
	}
</script>

<div
	class={`rounded-xl border-2 p-6 text-center transition-all hover:translate-y-[-5px] hover:shadow-md ${pet.isEgg ? 'border-amber-200 bg-amber-50' : 'border-gray-200'}`}
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

		{#if pet.isEgg}
			<div class="mt-2">
				{#if isNaming}
					<div class="flex gap-2">
						<input
							type="text"
							bind:value={nameInput}
							class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
							placeholder="Enter name..."
						/>
						<button on:click={submitName} class="rounded bg-blue-500 px-3 py-1 text-sm text-white">
							Name
						</button>
					</div>
				{:else}
					<button
						on:click={startNaming}
						class="w-full rounded bg-amber-500 px-2 py-1 text-sm text-white"
					>
						Name this egg
					</button>
				{/if}
			</div>
		{/if}

		<p class="mt-2 text-xs text-gray-500">Last updated: {pet.lastUpdated?.toLocaleString()}</p>
	</div>
</div>
