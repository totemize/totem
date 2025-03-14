import { derived, writable, type Writable } from 'svelte/store';
import { eventCache } from '../services/nostr';
import { pets } from './pets';

export const profiles: Writable<Set<string>> = writable(new Set());

export const currentStage = derived(profiles, ($profiles) => {
    // if($profiles.size === 0) {
    //     return 'egg';
    // }
    if($profiles.size === 1) {
        return 'intro';
    }
    if($profiles.size === 2) {
        return 'alive';
    }
    return 'egg'
});

