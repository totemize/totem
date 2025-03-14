import { NRelay1, NCache, type NostrEvent } from '@nostrify/nostrify';
import { processPetProfileEvent, processPetStatusEvent } from '$lib/stores/pets';

// Cache for deduplicating events
const eventCache = new NCache({ max: 1000 });

let relay: NRelay1 | null = null;

// Connect to the relay and set up subscriptions
export async function connectToRelay(relayUrl = 'ws://localhost:3334/nostr') {
	if (relay) {
		// Close existing connection if there is one
		try {
			await relay.close();
		} catch (e) {
			console.error('Error closing existing relay connection:', e);
		}
	}

	relay = new NRelay1(relayUrl);
	console.log('Connecting to relay:', relayUrl);

	// Set up pet profile subscription (kind 0)
	subscribeToPetProfiles();

	// Set up pet status subscription (kind 30078)
	subscribeToPetStatuses();

	return relay;
}

// Subscribe to pet profile metadata (kind 0)
async function subscribeToPetProfiles() {
	if (!relay) return;

	console.log('Subscribing to pet profiles...');

	try {
		for await (const msg of relay.req([{ kinds: [0] }])) {
			if (msg[0] === 'EVENT') {
				const event = msg[2] as NostrEvent;
				// Only process if we haven't seen this event before
				if (await processUniqueEvent(event)) {
					processPetProfileEvent(event);
				}
			}
		}
	} catch (error) {
		console.error('Error in pet profile subscription:', error);
		// Automatically reconnect if the subscription fails
		setTimeout(() => subscribeToPetProfiles(), 5000);
	}
}

// Subscribe to pet status updates (kind 30078)
async function subscribeToPetStatuses() {
	if (!relay) return;

	console.log('Subscribing to pet statuses...');

	try {
		for await (const msg of relay.req([{ kinds: [30078] }])) {
			if (msg[0] === 'EVENT') {
				const event = msg[2] as NostrEvent;
				// Only process if we haven't seen this event before
				if (await processUniqueEvent(event)) {
					processPetStatusEvent(event);
				}
			}
		}
	} catch (error) {
		console.error('Error in pet status subscription:', error);
		// Automatically reconnect if the subscription fails
		setTimeout(() => subscribeToPetStatuses(), 5000);
	}
}

// Helper to deduplicate events using the cache
async function processUniqueEvent(event: NostrEvent): Promise<boolean> {
	try {
		// Check if we've seen this event before
		const cachedEvents = await eventCache.query([{ ids: [event.id] }]);
		if (cachedEvents.length > 0) {
			return false; // Already processed
		}

		// Add to cache and return true to process
		await eventCache.event(event);
		return true;
	} catch (error) {
		console.error('Error checking event cache:', error);
		return true; // Process anyway if cache fails
	}
}

// Create a new pet (send create_egg command)
export async function createEgg() {
	if (!relay) {
		console.error('Relay not connected');
		return;
	}

	try {
		const event: NostrEvent = {
			kind: 5910,
			content: JSON.stringify({
				name: 'create_egg',
				parameters: {}
			}),
			tags: [['c', 'execute-tool']],
			created_at: Math.floor(Date.now() / 1000),
			pubkey: 'dummy', // Will be replaced with user's pubkey
			id: 'dummy', // Will be calculated
			sig: 'dummy' // Will be generated
		};

		// The library will automatically sign and complete the event
		await relay.event(event);
		console.log('Create egg command sent');
	} catch (error) {
		console.error('Error creating egg:', error);
	}
}

// Name a pet (send name_pet command)
export async function namePet(name: string, petId?: string) {
	if (!relay) {
		console.error('Relay not connected');
		return;
	}

	try {
		const params: any = { name };
		if (petId) {
			params.pet_id = petId;
		}

		const event: NostrEvent = {
			kind: 5910,
			content: JSON.stringify({
				name: 'name_pet',
				parameters: params
			}),
			tags: [['c', 'execute-tool']],
			created_at: Math.floor(Date.now() / 1000),
			pubkey: 'dummy', // Will be replaced with user's pubkey
			id: 'dummy', // Will be calculated
			sig: 'dummy' // Will be generated
		};

		// The library will automatically sign and complete the event
		await relay.event(event);
		console.log('Name pet command sent:', name);
	} catch (error) {
		console.error('Error naming pet:', error);
	}
}
