<script lang="ts">
	import { connectionStatus, pubkey } from '$lib/services/nostr';
	import { goto } from '$app/navigation';

	let isCreatingEgg = false;

	async function handleCreateEgg() {
		goto('/dash');
	}
</script>

<main class="container mx-auto max-w-4xl px-4 py-8">
	<h1 class="mb-2 text-center text-3xl font-bold">Totem Relay</h1>

	<div class="mb-6 flex items-center justify-center gap-2">
		{#if $connectionStatus === 'connected'}
			<div class="flex items-center gap-1">
				<span class="inline-block h-2 w-2 rounded-full bg-green-500"></span>
				<span class="text-sm text-green-700">Connected</span>
			</div>
			<div class="mb-6 flex justify-center">
				<button
					class="rounded-md bg-green-500 px-4 py-2 text-white transition-colors hover:bg-green-600 disabled:opacity-70"
					on:click={handleCreateEgg}
					disabled={isCreatingEgg}
				>
					'Goto Egg'
				</button>
			</div>
		{:else if $connectionStatus === 'connecting'}
			<div class="flex items-center gap-1">
				<span class="inline-block h-2 w-2 animate-pulse rounded-full bg-yellow-500"></span>
				<span class="text-sm text-yellow-700">Connecting...</span>
			</div>
		{:else}
			<div class="flex items-center gap-1">
				<span class="inline-block h-2 w-2 rounded-full bg-red-500"></span>
				<span class="text-sm text-red-700">Disconnected</span>
			</div>
		{/if}

		{#if $pubkey}
			<span class="text-xs text-gray-500"
				>ID: {$pubkey.substring(0, 6)}...{$pubkey.substring($pubkey.length - 4)}</span
			>
		{/if}
	</div>
</main>
