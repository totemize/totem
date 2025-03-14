<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';
	import { connectToRelay } from '$lib/services/nostr';
	let { children } = $props();

	onMount(() => {
		connectToRelay().catch((err) => {
			console.error('Connection error in mount:', err);
		});
	});
</script>

{@render children()}
