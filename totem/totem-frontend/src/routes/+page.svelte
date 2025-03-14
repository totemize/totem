<script lang="ts">
	import { onMount } from 'svelte';
	import { connectToRelay, createEgg } from '$lib/services/nostr';
	import { pets } from '$lib/stores/pets';
	import Pet from './Pet.svelte';

	let isConnected = false;
	let connectionError = '';

	onMount(async () => {
		try {
			await connectToRelay();
			isConnected = true;
		} catch (error) {
			console.error('Failed to connect to relay:', error);
			connectionError = 'Failed to connect to relay. Please try again.';
		}
	});

	// Create a sorted array of pets from the store
	$: sortedPets = Object.values($pets).sort((a, b) => {
		// First show non-eggs, then sort by last update time
		if (a.isEgg && !b.isEgg) return 1;
		if (!a.isEgg && b.isEgg) return -1;
		return b.lastUpdated.getTime() - a.lastUpdated.getTime();
	});
</script>

<main class="container mx-auto max-w-4xl px-4 py-8">
	<h1 class="mb-6 text-center text-3xl font-bold">Totem Relay</h1>

	{#if connectionError}
		<div class="my-4 rounded-md bg-red-100 p-4 text-red-700">
			{connectionError}
			<button
				class="ml-4 rounded bg-red-500 px-3 py-1 text-sm text-white"
				on:click={() => location.reload()}
			>
				Retry
			</button>
		</div>
	{:else if !isConnected}
		<div class="my-4 rounded-md bg-blue-100 p-4 text-center text-blue-700">
			Connecting to relay...
		</div>
	{:else}
		<div class="mb-6 flex justify-center">
			<button
				class="rounded-md bg-green-500 px-4 py-2 text-white transition-colors hover:bg-green-600"
				on:click={createEgg}
			>
				Create New Egg
			</button>
		</div>

		{#if sortedPets.length === 0}
			<div class="my-8 rounded-lg bg-gray-100 p-8 text-center">
				<h2 class="mb-2 text-xl font-bold">No Pets Yet!</h2>
				<p class="mb-4">Create your first pet by clicking the button above.</p>
			</div>
		{:else}
			<div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
				{#each sortedPets as pet (pet.pubkey)}
					<Pet {pet} />
				{/each}
			</div>
		{/if}

		<div class="mt-12 rounded-lg bg-gray-100 p-6">
			<h2 class="mb-4 text-xl font-bold">About Totem Relay</h2>
			<p>
				Totem Relay is a Nostr relay with virtual pets similar to Tamagotchi. Your pets will grow
				and change based on your interactions.
			</p>
			<p class="mt-2">
				Connected to: <code class="rounded bg-gray-200 px-2 py-1 text-sm"
					>ws://localhost:3334/nostr</code
				>
			</p>
		</div>
	{/if}
</main>
