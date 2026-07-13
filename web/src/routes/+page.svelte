<script lang="ts">
  import { onDestroy } from 'svelte';
  import type Sigma from 'sigma';
  import { buildGraph } from '$lib/graph';
  import type { EgoNetwork } from '$lib/types';
  import { version } from '../../package.json';

  let started = $state(false);
  let lang = $state('en');
  let headword = $state('etymology');
  let randomLang = $state('');
  let error = $state<string | null>(null);
  let container: HTMLDivElement = $state()!;
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
    const query = randomLang ? `?lang=${encodeURIComponent(randomLang)}` : '';
    const res = await fetch(`/api/random${query}`);
    if (!res.ok) return;
    const pick: { langCode: string; headword: string } = await res.json();
    lang = pick.langCode;
    headword = pick.headword;
    search();
  }

  function begin() {
    started = true;
    search();
  }

  onDestroy(() => renderer?.kill());
</script>

<svelte:head>
  <title>Etymyriad</title>
  <meta
    name="description"
    content="An interactive graph of words and their origins."
  />
  <link
    href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@700&display=swap"
    rel="stylesheet"
  />
</svelte:head>

<main>
  {#if started}
    <form
      onsubmit={(e) => {
        e.preventDefault();
        search();
      }}
    >
      <h1>Etymyriad</h1>
      <input aria-label="Language code" bind:value={lang} placeholder="en" />
      <input
        aria-label="Headword"
        bind:value={headword}
        placeholder="etymology"
      />
      <button type="submit">Search</button>
      <input
        class="random-lang"
        aria-label="Random language filter"
        bind:value={randomLang}
        placeholder="random language code"
      />
      <button type="button" onclick={randomWord}>Random</button>
    </form>

    {#if error}
      <p class="error">{error}</p>
    {/if}

    <div class="canvas" bind:this={container}></div>
  {:else}
    <div class="landing">
      <h1>Etymyriad</h1>
      <p class="lead">An interactive graph of words and their origins.</p>
      <p class="lead">
        Trace the etymology of any <i>lexeme</i> (word) in any language back
        through each <i>etymon</i> (word ancestor) that influenced it, and explore
        its cognates, derivatives, and roots!
      </p>
      <button type="button" onclick={begin}>Begin</button>
    </div>
  {/if}

  <p class="version">v{version}</p>
</main>

<style>
  :global(html, body) {
    margin: 0;
    height: 100%;
    overflow: hidden;
  }
  main {
    display: flex;
    flex-direction: column;
    height: 100vh;
    font-family: system-ui, sans-serif;
  }
  form {
    position: relative;
    padding: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  h1 {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    margin: 0;
    font-family: 'Libre Baskerville', serif;
    font-weight: 700;
    font-size: 1.5rem;
    letter-spacing: 0.05em;
  }
  .random-lang {
    margin-left: auto;
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
  .landing {
    margin: auto;
    max-width: 32rem;
    padding: 0 1rem;
    text-align: center;
  }
  .landing h1 {
    position: static;
    transform: none;
    font-size: 2.5rem;
  }
  .landing .lead {
    margin-top: 1rem;
    line-height: 1.5;
  }
  .landing button {
    margin-top: 2rem;
    padding: 0.5rem 1.5rem;
    font-size: 1rem;
  }
  .version {
    position: fixed;
    right: 0;
    bottom: 0;
    margin: 0;
    padding: 0.15rem 0.6rem;
    font-family: monospace;
    font-size: 0.75rem;
    color: #999;
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 4px 0 0 0;
  }
</style>
