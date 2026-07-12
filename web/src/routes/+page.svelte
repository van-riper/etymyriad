<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type Sigma from 'sigma';
  import { buildGraph } from '$lib/graph';
  import type { EgoNetwork } from '$lib/types';

  let lang = $state('en');
  let headword = $state('water');
  let randomLang = $state('');
  let error = $state<string | null>(null);
  let container: HTMLDivElement;
  let renderer: Sigma | null = null;

  // Sigma needs WebGL, which only exists in the browser -- a static import
  // would crash SvelteKit's SSR render of this page, so load it lazily here.
  async function search() {
    error = null;
    const res = await fetch(
      `/api/word/${encodeURIComponent(lang)}/${encodeURIComponent(headword)}?depth=2`,
    );

    renderer?.kill();
    renderer = null;

    if (!res.ok) {
      error = `No lexeme found for ${lang}:${headword}`;
      return;
    }

    const network: EgoNetwork = await res.json();
    const { default: Sigma } = await import('sigma');
    const graph = buildGraph(network);
    renderer = new Sigma(graph, container);
    renderer.on('clickNode', ({ node }) => {
      const clickedHeadword = graph.getNodeAttribute(node, 'headword');
      const clickedLang = graph.getNodeAttribute(node, 'langCode');
      if (clickedLang === lang && clickedHeadword === headword) return;
      lang = clickedLang;
      headword = clickedHeadword;
      search();
    });
  }

  async function randomWord() {
    const query = randomLang
      ? `?lang=${encodeURIComponent(randomLang)}`
      : '';
    const res = await fetch(`/api/random${query}`);
    if (!res.ok) return;
    const pick: { langCode: string; headword: string } = await res.json();
    lang = pick.langCode;
    headword = pick.headword;
    search();
  }

  onMount(search);
  onDestroy(() => renderer?.kill());
</script>

<svelte:head>
  <title>etymyriad: a myriad of word origins</title>
  <meta
    name="description"
    content="An interactive graph of words and their origins."
  />
</svelte:head>

<main>
  <form
    onsubmit={(e) => {
      e.preventDefault();
      search();
    }}
  >
    <input aria-label="Language code" bind:value={lang} placeholder="en" />
    <input
      aria-label="Headword"
      bind:value={headword}
      placeholder="water"
    />
    <button type="submit">Search</button>
    <button type="button" onclick={randomWord}>Random</button>
    <input
      aria-label="Random language filter"
      bind:value={randomLang}
      placeholder="random language code"
    />
  </form>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  <div class="canvas" bind:this={container}></div>
</main>

<style>
  :global(html, body) {
    margin: 0;
    height: 100%;
  }
  main {
    display: flex;
    flex-direction: column;
    height: 100vh;
    font-family: system-ui, sans-serif;
  }
  form {
    padding: 1rem;
    display: flex;
    gap: 0.5rem;
  }
  .error {
    padding: 0 1rem;
    color: #c0392b;
  }
  .canvas {
    flex: 1;
    width: 100%;
    border-top: 1px solid #ddd;
  }
</style>
