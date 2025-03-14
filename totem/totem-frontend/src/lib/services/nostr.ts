// src/lib/services/nostr.ts
import { NRelay1, NCache, NSecSigner, type NostrEvent } from '@nostrify/nostrify';
import { processPetProfileEvent, processPetStatusEvent } from '$lib/stores/pets';
import { writable } from 'svelte/store';

// Store our connection state and user keys
export const connectionStatus = writable<'disconnected' | 'connecting' | 'connected'>(
	'disconnected'
);
export const connectionError = writable<string | null>(null);

// Generate or load private key
// In a real app, you'd use a more secure storage method
function getOrCreatePrivateKey(): Uint8Array {
	const storedKey = localStorage.getItem('totem-private-key');
	if (storedKey) {
		return new Uint8Array(JSON.parse(storedKey));
	}

	// Create a new random key (in real app, use a proper key generation library)
	const key = crypto.getRandomValues(new Uint8Array(32));
	localStorage.setItem('totem-private-key', JSON.stringify(Array.from(key)));
	return key;
}

// Cache for deduplicating events
export const eventCache = new NCache({ max: 1000 });

// Relay and signer
let relay: NRelay1 | null = null;
let signer: NSecSigner | null = null;
export const pubkey = writable<string | null>(null);

// Connect to the relay and set up subscriptions
export async function connectToRelay(relayUrl = 'ws://localhost:3334/nostr') {
	connectionStatus.set('connecting');
	connectionError.set(null);

	try {
		if (relay) {
			// Close existing connection if there is one
			try {
				await relay.close();
			} catch (e) {
				console.error('Error closing existing relay connection:', e);
			}
		}

		// Initialize our signer with private key
		const privateKey = getOrCreatePrivateKey();
		signer = new NSecSigner(privateKey);

		// Get public key and update the store
		const userPubkey = await signer.getPublicKey();
		pubkey.set(userPubkey);

		// Initialize relay connection
		relay = new NRelay1(relayUrl);
		console.log('Connecting to relay:', relayUrl);

		// Set up subscriptions
		subscribeToEvents();

		connectionStatus.set('connected');
		return relay;
	} catch (error) {
		console.error('Failed to connect to relay:', error);
		connectionStatus.set('disconnected');
		connectionError.set(error instanceof Error ? error.message : 'Unknown error');
		throw error;
	}
}

// Subscribe to both profiles and status events
async function subscribeToEvents() {
	if (!relay) return;

	console.log('Setting up subscriptions...');

	// Subscribe to pet profiles
	subscribeToProfiles();

	// Subscribe to pet status updates
	subscribeToStatusUpdates();
}

// Subscribe to pet profile metadata (kind 0)
async function subscribeToProfiles() {
	if (!relay) return;

	console.log('Subscribing to pet profiles...');

	try {
		for await (const msg of relay.req([{ kinds: [0] }])) {
			if (msg[0] === 'EVENT') {
				const event = msg[2] as NostrEvent;
				console.log('new profile event', event);
				if (await processUniqueEvent(event)) {
					processPetProfileEvent(event);
				}
			}
		}
	} catch (error) {
		console.error('Error in pet profile subscription:', error);
		setTimeout(() => subscribeToProfiles(), 5000);
	}
}

// Subscribe to pet status updates (kind 30078)
async function subscribeToStatusUpdates() {
	if (!relay) return;

	console.log('Subscribing to pet statuses...');

	try {
		for await (const msg of relay.req([{ kinds: [30078] }])) {
			if (msg[0] === 'EVENT') {
				const event = msg[2] as NostrEvent;
				if (await processUniqueEvent(event)) {
					processPetStatusEvent(event);
				}
			}
		}
	} catch (error) {
		console.error('Error in pet status subscription:', error);
		setTimeout(() => subscribeToStatusUpdates(), 5000);
	}
}

// Helper to deduplicate events using the cache
async function processUniqueEvent(event: NostrEvent): Promise<boolean> {
	try {
		// For metadata (kind 0) events, check by pubkey to get the latest profile
		if (event.kind === 0) {
			// Query for any existing metadata events for this pubkey
			const existingProfiles = await eventCache.query([{ kinds: [0], authors: [event.pubkey] }]);

			// If we found existing profiles, keep only the newest one
			if (existingProfiles.length > 0) {
				// Sort by creation time (newest first)
				existingProfiles.sort((a, b) => b.created_at - a.created_at);

				// If this event is older than our newest cached one, skip it
				if (existingProfiles[0].created_at >= event.created_at) {
					return false; // Skip older event
				}

				// This is newer, so remove old ones and add this one
				for (const oldEvent of existingProfiles) {
					eventCache.delete(oldEvent);
				}
			}
		}

		// For status events (kind 30078), replace older ones for the same pet
		if (event.kind === 30078) {
			// Find any existing status events for this pet
			const existingStatuses = await eventCache.query([
				{ kinds: [30078], authors: [event.pubkey] }
			]);

			// Remove all older status events for this pet
			for (const oldEvent of existingStatuses) {
				eventCache.delete(oldEvent);
			}
		}

		// Add the new event to cache
		await eventCache.event(event);
		return true; // Process this event
	} catch (error) {
		console.error('Error checking event cache:', error);
		return true; // Process anyway if cache fails
	}
}

// Create and publish a signed event
async function publishEvent(kind: number, content: string, tags: string[][]): Promise<boolean> {
	if (!relay || !signer) {
		console.error('Relay or signer not initialized');
		return false;
	}

	try {
		// Create event template
		const eventTemplate = {
			kind,
			content,
			tags,
			created_at: Math.floor(Date.now() / 1000)
		};

		// Sign the event with our private key
		const signedEvent = await signer.signEvent(eventTemplate);

		// Publish the signed event
		await relay.event(signedEvent);
		return true;
	} catch (error) {
		console.error('Error publishing event:', error);
		return false;
	}
}

// Create a new pet (send create_egg command)
export async function createEgg(): Promise<boolean> {
	const content = JSON.stringify({
		name: 'create_egg',
		parameters: {}
	});

	return publishEvent(5910, content, [['c', 'execute-tool']]);
}

// Name a pet (send name_pet command)
export async function namePet(name: string, petId?: string): Promise<boolean> {
	const params: any = { name };
	if (petId) {
		params.pet_id = petId;
	}

	const content = JSON.stringify({
		name: 'name_pet',
		parameters: params
	});

	return publishEvent(5910, content, [['c', 'execute-tool']]);
}

// Direct interaction with pet (sends a note to feed the pet)
export async function interactWithPet(
	petPubkey: string,
	message: string = 'Feeding you!'
): Promise<boolean> {
	return publishEvent(1, message, [['p', petPubkey]]);
}
