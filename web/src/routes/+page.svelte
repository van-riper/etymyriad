<script lang="ts">
	// Landing page placeholder. The interactive graph explorer lands here later
	// (a Sigma.js canvas backed by /api/word/:lang/:headword).
	let query = $state('');
</script>

<svelte:head>
	<title>etymyriad: a myriad of word origins</title>
	<meta
		name="description"
		content="Explore the ancestry, descendants, and cognates of words as an interactive etymology network."
	/>
</svelte:head>

<main>
	<h1>etymyriad</h1>
	<p>A myriad of word origins, as an interactive network.</p>

	<form method="GET" action="/" role="search">
		<input
			type="search"
			name="q"
			bind:value={query}
			placeholder="Try a word, e.g. water"
			aria-label="Search for a word"
		/>
		<button type="submit">Explore</button>
	</form>

	<p class="hint">
		Scaffold in place. Next: wire this search to the graph explorer.
	</p>
</main>

<style>
	main {
		max-width: 40rem;
		margin: 4rem auto;
		padding: 0 1rem;
		font-family: system-ui, sans-serif;
	}
	h1 {
		margin-bottom: 0.25rem;
	}
	.hint {
		margin-top: 2rem;
		color: #666;
		font-size: 0.9rem;
	}
</style>
