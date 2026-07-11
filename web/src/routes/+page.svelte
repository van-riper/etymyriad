<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type Sigma from 'sigma';
  import { buildGraph } from '$lib/graph';
  import type { EgoNetwork } from '$lib/types';

  let lang = $state('en');
  let headword = $state('water');
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
  <h1>etymyriad</h1>

  <p class="lead">
    An interactive graph of words and their origins. Trace the etymology of any
    word back through each language that influenced it and explore their
    relations to other words stemming from the same roots and meanings.
  </p>

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
  </form>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  <div class="canvas" bind:this={container}></div>
</main>

<style>
  main {
    max-width: 40rem;
    margin: 6rem auto;
    padding: 0 1rem;
    font-family: system-ui, sans-serif;
    line-height: 1.5;
  }
  h1 {
    margin-bottom: 0.25rem;
    font-size: 2.5rem;
  }
  .lead {
    margin-top: 2rem;
    font-size: 1.05rem;
  }
  form {
    margin-top: 2rem;
    display: flex;
    gap: 0.5rem;
  }
  .error {
    margin-top: 1rem;
    color: #c0392b;
  }
  .canvas {
    margin-top: 1.5rem;
    width: 100%;
    height: 32rem;
    border: 1px solid #ddd;
  }
</style>
