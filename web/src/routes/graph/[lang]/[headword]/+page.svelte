<script lang="ts">
  import { onDestroy } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import type Sigma from 'sigma';
  import { buildGraph } from '$lib/graph';
  import type { EgoNetwork } from '$lib/types';
  import Badges from '$lib/Badges.svelte';

  let lang = $state(page.params.lang as string);
  let headword = $state(page.params.headword as string);
  let randomLang = $state('');
  let error = $state<string | null>(null);
  let container: HTMLDivElement = $state()!;
  let renderer: Sigma | null = null;

  // Sigma needs WebGL, which only exists in the browser -- a static import
  // would crash SvelteKit's SSR render of this page, so load it lazily here.
  async function loadNetwork(currentLang: string, currentHeadword: string) {
    error = null;
    const res = await fetch(
      `/api/word/${encodeURIComponent(currentLang)}/${encodeURIComponent(currentHeadword)}?depth=2`,
    );

    renderer?.kill();
    renderer = null;

    if (!res.ok) {
      error = `No lexeme found for ${currentLang}:${currentHeadword}`;
      return;
    }

    const network: EgoNetwork = await res.json();
    const { default: Sigma } = await import('sigma');
    const graph = buildGraph(network);
    renderer = new Sigma(graph, container);
    renderer.on('clickNode', ({ node }) => {
      const clickedHeadword = graph.getNodeAttribute(node, 'headword');
      const clickedLang = graph.getNodeAttribute(node, 'langCode');
      if (clickedLang === currentLang && clickedHeadword === currentHeadword) {
        return;
      }
      goto(
        `/graph/${encodeURIComponent(clickedLang)}/${encodeURIComponent(clickedHeadword)}`,
      );
    });
  }

  // The route params are the single source of truth for what's rendered.
  // The form fields below are just an editable draft the user can type
  // into before submitting, so this effect ignores their local state and
  // only reacts to navigation (search submit, node click, random word).
  $effect(() => {
    lang = page.params.lang as string;
    headword = page.params.headword as string;
    loadNetwork(page.params.lang as string, page.params.headword as string);
  });

  async function randomWord() {
    const query = randomLang ? `?lang=${encodeURIComponent(randomLang)}` : '';
    const res = await fetch(`/api/random${query}`);
    if (!res.ok) return;
    const pick: { langCode: string; headword: string } = await res.json();
    goto(
      `/graph/${encodeURIComponent(pick.langCode)}/${encodeURIComponent(pick.headword)}`,
    );
  }

  function search() {
    goto(`/graph/${encodeURIComponent(lang)}/${encodeURIComponent(headword)}`);
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
  <form
    onsubmit={(e) => {
      e.preventDefault();
      search();
    }}
  >
    <button class="search-btn" type="submit">Search</button>
    <h1>Etymyriad</h1>
    <input
      class="headword-input"
      aria-label="Headword"
      bind:value={headword}
      placeholder="etymology"
    />
    <input
      class="lang-input"
      aria-label="Language code"
      bind:value={lang}
      placeholder="en"
    />
    <span class="random-lang-label">Language filter:</span>
    <input
      class="lang-input"
      aria-label="Random language filter"
      bind:value={randomLang}
      placeholder={lang || 'any'}
    />
    <button class="random-btn" type="button" onclick={randomWord}
      >Random</button
    >
  </form>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  <div class="canvas" bind:this={container}></div>

  <Badges />
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
  input,
  button {
    font-family: inherit;
    font-size: 1rem;
  }
  .lang-input {
    width: 6ch;
    flex-shrink: 0;
  }
  .headword-input {
    width: 12rem;
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
  .random-lang-label {
    margin-left: auto;
    color: #666;
  }
  .search-btn {
    margin-right: 1em;
  }
  .random-btn {
    margin-left: 1em;
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
