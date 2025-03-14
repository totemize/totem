<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';
	import { goto } from '$app/navigation';
	import { eventCache, connectToRelay } from '$lib/services/nostr';
	import { writable, type Writable } from 'svelte/store';
	import { currentStage, profiles } from '../lib/stores/stage';
	let { children } = $props();

	let activeStage: Writable<string> = writable('egg');
	
	onMount(async () => {
		goto(`/${$currentStage}`);
		await connectToRelay().catch((err) => {
			console.error('Connection error in mount:', err);
		});
		for(const event of eventCache) {
			if(event.kind === 0) {
				profiles.update((prev) => {
					prev.add(event.pubkey);
					return prev;
				});
			}
		}
		currentStage.subscribe((stage) => {
			if($activeStage === stage) return 
			goto(`/${stage}`);
			activeStage.set(stage as string);
		});
	});
	
</script>

{$currentStage}

{@render children()}
