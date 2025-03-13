<script>
	import { onMount, onDestroy } from 'svelte';
	import { Relay } from 'nostr-tools/relay';
	import Pet from './Pet.svelte';

	// Reactive state for pets
	let pets = $state([]);
	let connected = $state(false);
	let relay;

	async function connectToRelay() {
		try {
			relay = await Relay.connect('ws://localhost:3334/nostr');
			connected = true;
			console.log(`Connected to ${relay.url}`);

			// Subscribe to kind 0 (profiles) and kind 30078 (statuses) events
			const subscription = relay.subscribe(
				[
					{
						kinds: [0, 30078]
					}
				],
				{
					onevent(event) {
						// console.log('Event received:', event);
						if (event.kind === 30078) {
							handlePetStatusEvent(event);
						} else if (event.kind === 0) {
							handleProfileEvent(event);
						}
					},
					oneose() {
						console.log('EOSE received - subscription complete');
					}
				}
			);
		} catch (error) {
			console.error('Failed to connect to relay:', error);
		}
	}

	function handlePetStatusEvent(event) {
		try {
			// Extract pet data from tags
			const petData = {
				energy: parseFloat(findTagValue(event.tags, 'energy') || '0'),
				happiness: parseFloat(findTagValue(event.tags, 'happiness') || '0'),
				lastFed: findTagValue(event.tags, 'last_fed') || '',
				name: findTagValue(event.tags, 'name') || 'Unnamed',
				stateEmoji: findTagValue(event.tags, 'state_emoji') || '🥚'
			};
			console.log(petData);
			// Check if the pet already exists in our array
			const existingPetIndex = pets.findIndex((p) => p.pubkey === event.pubkey);

			if (existingPetIndex >= 0) {
				// Update existing pet
				pets[existingPetIndex] = {
					...pets[existingPetIndex],
					...petData,
					lastUpdated: new Date(event.created_at * 1000)
				};
			} else {
				// Add new pet
				pets = [
					...pets,
					{
						pubkey: event.pubkey,
						...petData,
						lastUpdated: new Date(event.created_at * 1000)
					}
				];
			}
		} catch (error) {
			console.error('Error handling pet status event:', error, event);
		}
	}

	function handleProfileEvent(event) {
		try {
			// Parse the profile data from content
			const profileData = JSON.parse(event.content);

			// Check if the pet/profile already exists
			const existingPetIndex = pets.findIndex((p) => p.pubkey === event.pubkey);

			if (existingPetIndex >= 0) {
				// Update existing pet with profile data
				pets[existingPetIndex] = {
					...pets[existingPetIndex],
					name: profileData.name || pets[existingPetIndex].name,
					about: profileData.about,
					lastUpdated: new Date(event.created_at * 1000)
				};
			} else {
				// Add new pet from profile
				pets = [
					...pets,
					{
						pubkey: event.pubkey,
						name: profileData.name || 'Unnamed',
						about: profileData.about,
						energy: 0,
						happiness: 0,
						stateEmoji: '🥚',
						lastUpdated: new Date(event.created_at * 1000)
					}
				];
			}
		} catch (error) {
			console.error('Error handling profile event:', error, event);
		}
	}

	// Helper function to find value in tags
	function findTagValue(tags, key) {
		const tag = tags.find((tag) => tag[0] === key);
		return tag ? tag[1] : null;
	}

	onMount(() => {
		connectToRelay();
	});

	onDestroy(() => {
		if (relay) {
			relay.close();
			console.log('Relay connection closed');
		}
	});
</script>

<main class="container mx-auto max-w-4xl px-4 py-8">
	<h1 class="mb-6 text-center text-3xl font-bold">Totem Relay</h1>

	{#if connected}
		<div class="mb-6 rounded bg-green-100 px-4 py-2 text-center">
			Connected to relay: ws://localhost:3334/nostr
		</div>
	{:else}
		<div class="mb-6 rounded bg-red-100 px-4 py-2 text-center">
			Not connected to relay. Attempting to connect...
		</div>
	{/if}

	{#if pets.length > 0}
		<div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
			{#each pets as pet (pet.pubkey)}
				<Pet {pet} />
			{/each}
		</div>
	{:else}
		<div class="my-8 rounded-lg bg-gray-50 py-12 text-center">
			<h2 class="text-2xl font-bold">No Pets Yet!</h2>
			<p class="mt-2">Create your first pet by sending a pet creation event to this relay.</p>
		</div>
	{/if}
</main>
