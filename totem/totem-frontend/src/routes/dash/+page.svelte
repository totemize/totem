<script>
	import {
		connectToRelay,
		createEgg,
		connectionStatus,
		connectionError
	} from '$lib/services/nostr';
	import { eggPets, hatchedPets, petsArray } from '$lib/stores/pets';
	import Pet from '../Pet.svelte';
	let isCreatingEgg = false;

	async function handleCreateEgg() {
		isCreatingEgg = true;
		try {
			await createEgg();
		} catch (error) {
			console.error('Error creating egg:', error);
		} finally {
			setTimeout(() => {
				isCreatingEgg = false;
			}, 1000);
		}
	}
</script>

{#if $connectionError}
	<div class="my-4 rounded-md bg-red-100 p-4 text-red-700">
		{$connectionError}
		<button
			class="ml-4 rounded bg-red-500 px-3 py-1 text-sm text-white transition-colors hover:bg-red-600"
			on:click={() => connectToRelay()}
		>
			Retry
		</button>
	</div>
{:else if $connectionStatus !== 'connected'}
	<div class="my-4 rounded-md bg-blue-100 p-4 text-center text-blue-700">
		Connecting to relay...
	</div>
{:else}
	<div class="mb-6 flex justify-center">
		<button
			class="rounded-md bg-green-500 px-4 py-2 text-white transition-colors hover:bg-green-600 disabled:opacity-70"
			on:click={handleCreateEgg}
			disabled={isCreatingEgg}
		>
			{isCreatingEgg ? 'Creating...' : 'Create New Egg'}
		</button>
	</div>

	{#if $petsArray.length === 0}
		<div class="my-8 rounded-lg bg-gray-100 p-8 text-center">
			<h2 class="mb-2 text-xl font-bold">No Pets Yet!</h2>
			<p class="mb-4">Create your first pet by clicking the button above.</p>
		</div>
	{:else}
		<!-- Pet counters -->
		<div class="mb-4 flex justify-center gap-4 text-sm">
			{#if $hatchedPets.length > 0}
				<div class="rounded-full bg-blue-100 px-3 py-1">
					🐱 {$hatchedPets.length} Active Pet{$hatchedPets.length !== 1 ? 's' : ''}
				</div>
			{/if}

			{#if $eggPets.length > 0}
				<div class="rounded-full bg-amber-100 px-3 py-1">
					🥚 {$eggPets.length} Egg{$eggPets.length !== 1 ? 's' : ''}
				</div>
			{/if}
		</div>

		<!-- Pet grid -->
		<div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
			{#each $petsArray as pet (pet.pubkey)}
				<Pet {pet} />
			{/each}
		</div>
	{/if}

	<div class="mt-12 rounded-lg bg-gray-100 p-6">
		<h2 class="mb-4 text-xl font-bold">About Totem Relay</h2>
		<p>
			Totem Relay is a Nostr relay with virtual pets similar to Tamagotchi. Your pets will grow and
			change based on your interactions.
		</p>
		<p class="mt-2">
			Connected to: <code class="rounded bg-gray-200 px-2 py-1 text-sm"
				>ws://localhost:3334/nostr</code
			>
		</p>
	</div>
{/if}
