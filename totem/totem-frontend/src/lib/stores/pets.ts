// src/lib/stores/pets.ts
import { writable, derived } from 'svelte/store';
import type { NostrEvent } from '@nostrify/nostrify';

export interface Pet {
	pubkey: string;
	name: string;
	about?: string;
	energy: number;
	happiness: number;
	lastFed: string;
	stateEmoji: string;
	isEgg: boolean;
	lastUpdated: Date;
}

// Main store for all pets
export const pets = writable<Record<string, Pet>>({});

// Derived stores for better usability
export const petsArray = derived(pets, ($pets) => Object.values($pets));

export const eggPets = derived(petsArray, ($petsArray) => $petsArray.filter((pet) => pet.isEgg));

export const hatchedPets = derived(petsArray, ($petsArray) =>
	$petsArray.filter((pet) => !pet.isEgg)
);

// Extract pet profile info from kind 0 events
export function processPetProfileEvent(event: NostrEvent) {
	try {
		const content = JSON.parse(event.content);
		const isEgg = content.about?.includes('egg waiting to be named') || false;

		pets.update((currentPets) => {
			// Check if we already have this pet
			const existingPet = currentPets[event.pubkey];

			// Create or update the pet with profile data
			const updatedPet: Pet = {
				...existingPet,
				pubkey: event.pubkey,
				name: content.name || 'Unnamed Pet',
				about: content.about,
				energy: existingPet?.energy || 100,
				happiness: existingPet?.happiness || 100,
				lastFed: existingPet?.lastFed || new Date().toLocaleString(),
				stateEmoji: isEgg ? '🥚' : existingPet?.stateEmoji || '😊',
				isEgg: isEgg,
				lastUpdated: new Date()
			};

			return { ...currentPets, [event.pubkey]: updatedPet };
		});
	} catch (error) {
		console.error('Error processing pet profile:', error);
	}
}

// Update pet stats from kind 30078 events
export function processPetStatusEvent(event: NostrEvent) {
	try {
		// Extract tag values
		const getTagValue = (tagName: string): string | undefined => {
			const tag = event.tags.find((t) => t[0] === tagName);
			return tag ? tag[1] : undefined;
		};

		const energy = parseFloat(getTagValue('energy') || '0');
		const happiness = parseFloat(getTagValue('happiness') || '0');
		const lastFed = getTagValue('last_fed') || '';
		const name = getTagValue('name') || '';
		const stateEmoji = getTagValue('state_emoji') || '😊';

		pets.update((currentPets) => {
			// Check if we already have this pet
			const existingPet = currentPets[event.pubkey];

			if (!existingPet) {
				// Create new pet if it doesn't exist
				const newPet: Pet = {
					pubkey: event.pubkey,
					name: name,
					energy: energy,
					happiness: happiness,
					lastFed: lastFed,
					stateEmoji: stateEmoji,
					isEgg: false, // Status events are for hatched pets
					lastUpdated: new Date()
				};
				return { ...currentPets, [event.pubkey]: newPet };
			} else {
				// Update existing pet stats
				return {
					...currentPets,
					[event.pubkey]: {
						...existingPet,
						energy: energy,
						happiness: happiness,
						lastFed: lastFed,
						stateEmoji: stateEmoji,
						name: name || existingPet.name,
						lastUpdated: new Date()
					}
				};
			}
		});
	} catch (error) {
		console.error('Error processing pet status:', error);
	}
}
