<!-- src/routes/Pet.svelte -->
<script lang="ts">
	import { namePet, interactWithPet } from '$lib/services/nostr';
	import type { Pet } from '$lib/stores/pets';
	export let pet: Pet;

	// Reactive state
	let nameInput = '';
	let isNaming = false;
	let feedInput = '';
	let isFeeding = false;
	let actionInProgress = false;

	// Calculate time since last interaction for more user-friendly display
	function timeSinceLastFed(timeString) {
		// Handle missing or invalid timeString
		if (!timeString) return 'Never fed';

		try {
			// Create date object from the timeString
			const lastFedDate = new Date(timeString);

			// Validate that we have a proper date
			if (isNaN(lastFedDate.getTime())) {
				return 'Unknown';
			}

			const now = new Date();
			const diffMs = now.getTime() - lastFedDate.getTime();

			// Convert to minutes
			const diffMins = Math.floor(diffMs / 60000);

			if (diffMins < 1) return 'Just now';
			if (diffMins === 1) return '1 minute ago';
			if (diffMins < 60) return `${diffMins} minutes ago`;

			// Convert to hours
			const diffHrs = Math.floor(diffMins / 60);
			if (diffHrs === 1) return '1 hour ago';
			if (diffHrs < 24) return `${diffHrs} hours ago`;

			// Convert to days
			const diffDays = Math.floor(diffHrs / 24);
			if (diffDays === 1) return '1 day ago';
			return `${diffDays} days ago`;
		} catch (e) {
			// If any error occurs, return a fallback
			console.warn('Error parsing date:', e);
			return 'Unknown';
		}
	}

	// Format a date for direct display if needed
	function formatDate(timeString) {
		if (!timeString) return 'Never';

		try {
			const date = new Date(timeString);
			if (isNaN(date.getTime())) return timeString;

			return date.toLocaleString();
		} catch (e) {
			return timeString;
		}
	}

	// UI interaction handlers
	function startNaming() {
		isNaming = true;
		nameInput = '';
	}

	function startFeeding() {
		isFeeding = true;
		feedInput = "Here's some food!";
	}

	async function submitName() {
		if (nameInput.trim() && !actionInProgress) {
			actionInProgress = true;
			const success = await namePet(nameInput.trim(), pet.pubkey);
			if (success) {
				isNaming = false;
			}
			actionInProgress = false;
		}
	}

	async function submitFeed() {
		if (!actionInProgress) {
			actionInProgress = true;
			const message = feedInput.trim() || 'Feeding you!';
			const success = await interactWithPet(pet.pubkey, message);
			if (success) {
				isFeeding = false;
			}
			actionInProgress = false;
		}
	}

	// Status indicator based on pet's condition
	$: statusIndicator = getStatusIndicator(pet);

	function getStatusIndicator(pet: Pet) {
		if (pet.isEgg) return { color: 'bg-amber-500', text: 'Egg' };
		if (pet.energy < 30) return { color: 'bg-red-500', text: 'Hungry' };
		if (pet.happiness < 30) return { color: 'bg-red-500', text: 'Sad' };
		if (pet.energy > 80 && pet.happiness > 80) return { color: 'bg-green-500', text: 'Happy' };
		return { color: 'bg-blue-500', text: 'Good' };
	}
</script>

<div
	class={`rounded-xl border-2 p-6 text-center transition-all hover:translate-y-[-5px] hover:shadow-md 
		${pet.isEgg ? 'border-amber-200 bg-amber-50' : 'border-gray-200'}`}
>
	<!-- Pet emoji and name section -->
	<div class="mb-3 flex items-center justify-between">
		<div class="my-2 text-5xl">{pet.stateEmoji}</div>
		<div class="rounded-full px-2 py-1 text-xs text-white {statusIndicator.color}">
			{statusIndicator.text}
		</div>
	</div>

	<div class="mt-2 text-left">
		<h3 class="text-xl font-bold">{pet.name || 'Unnamed Egg'}</h3>
		<p class="my-1 text-xs text-gray-500">
			<code>{pet.pubkey.substring(0, 8)}...{pet.pubkey.substring(pet.pubkey.length - 4)}</code>
		</p>

		{#if pet.about}
			<p class="my-1 text-sm">{pet.about}</p>
		{/if}

		<!-- Stats section -->
		<div class="my-3 space-y-2">
			<div>
				<div class="flex justify-between text-sm">
					<span>Energy</span>
					<span>{pet.energy?.toFixed(1)}%</span>
				</div>
				<div class="h-2 overflow-hidden rounded bg-gray-200">
					<div
						class="h-full rounded transition-all duration-500 ease-out"
						class:bg-green-500={pet.energy >= 50}
						class:bg-yellow-500={pet.energy < 50 && pet.energy >= 30}
						class:bg-red-500={pet.energy < 30}
						style="width: {pet.energy}%;"
					></div>
				</div>
			</div>

			<div>
				<div class="flex justify-between text-sm">
					<span>Happiness</span>
					<span>{pet.happiness?.toFixed(1)}%</span>
				</div>
				<div class="h-2 overflow-hidden rounded bg-gray-200">
					<div
						class="h-full rounded transition-all duration-500 ease-out"
						class:bg-blue-500={pet.happiness >= 50}
						class:bg-yellow-500={pet.happiness < 50 && pet.happiness >= 30}
						class:bg-red-500={pet.happiness < 30}
						style="width: {pet.happiness}%;"
					></div>
				</div>
			</div>
		</div>

		<p class="my-1 text-sm">
			Last Fed:
			<span class="font-medium">
				{#if timeSinceLastFed(pet.lastFed) === 'Unknown'}
					{formatDate(pet.lastFed)}
				{:else}
					{timeSinceLastFed(pet.lastFed)}
				{/if}
			</span>
		</p>

		<!-- Interaction section -->
		<div class="mt-4 space-y-2">
			{#if pet.isEgg}
				{#if isNaming}
					<div class="flex gap-2">
						<input
							type="text"
							bind:value={nameInput}
							class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
							placeholder="Enter name..."
							disabled={actionInProgress}
						/>
						<button
							on:click={submitName}
							class="rounded bg-blue-500 px-3 py-1 text-sm text-white transition-colors hover:bg-blue-600 disabled:opacity-50"
							disabled={!nameInput.trim() || actionInProgress}
						>
							{actionInProgress ? '...' : 'Name'}
						</button>
					</div>
				{:else}
					<button
						on:click={startNaming}
						class="w-full rounded bg-amber-500 px-2 py-1 text-sm text-white transition-colors hover:bg-amber-600"
					>
						Name this egg
					</button>
				{/if}
			{:else if isFeeding}
				<div class="flex gap-2">
					<input
						type="text"
						bind:value={feedInput}
						class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
						placeholder="Message..."
						disabled={actionInProgress}
					/>
					<button
						on:click={submitFeed}
						class="rounded bg-green-500 px-3 py-1 text-sm text-white transition-colors hover:bg-green-600 disabled:opacity-50"
						disabled={actionInProgress}
					>
						{actionInProgress ? '...' : 'Feed'}
					</button>
				</div>
			{:else}
				<button
					on:click={startFeeding}
					class="w-full rounded bg-green-500 px-2 py-1 text-sm text-white transition-colors hover:bg-green-600"
				>
					Feed pet
				</button>
			{/if}
		</div>

		<p class="mt-2 text-xs text-gray-500">Updated: {pet.lastUpdated?.toLocaleString()}</p>
	</div>
</div>
