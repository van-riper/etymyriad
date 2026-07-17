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
        placeholder="any"
      />
      <button class="random-btn" type="button" onclick={randomWord}>Random</button>
    </form>

    {#if error}
      <p class="error">{error}</p>
    {/if}

    <div class="canvas" bind:this={container}></div>
  {:else}
    <div class="landing">
      <h1>Etymyriad</h1>
      <p class="author">By: Finn van Riper</p>
      <p class="lead">An interactive graph of words and their origins.</p>
      <p class="lead">
        Trace the etymology of any <i>lexeme</i> (word) in any language back
        through each <i>etymon</i> (word ancestor) that influenced it, and explore
        its cognates, derivatives, and roots!
      </p>
      <form
        class="landing-search"
        onsubmit={(e) => {
          e.preventDefault();
          begin();
        }}
      >
        <p class="landing-search-hint">
          Enter a word and language code, then hit Search.
        </p>
        <div class="landing-search-inputs">
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
        </div>
        <button type="submit">Search</button>
      </form>
    </div>
  {/if}

  <div class="badges">
    <p class="version">v{version}</p>
    <a
      class="github-link"
      href="https://github.com/van-riper/etymyriad"
      aria-label="View source on GitHub"
      target="_blank"
      rel="noreferrer"
    >
      <svg viewBox="0 0 16 16" width="20" height="20" fill="currentColor">
        <path
          d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
          0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
          -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
          .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
          -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0
          1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82
          1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01
          1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"
        />
      </svg>
    </a>
  </div>
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
  .author {
    margin: 0.5rem 0 0;
    font-size: 0.9rem;
    color: #666;
  }
  .landing .lead {
    margin-top: 1rem;
    line-height: 1.5;
  }
  .landing-search {
    margin-top: 1rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
  }
  .landing-search-hint {
    margin: 0;
    font-size: 0.95rem;
    color: #666;
  }
  .landing-search-inputs {
    margin-top: 0.5rem;
    display: flex;
    gap: 0.5rem;
  }
  .landing-search button {
    margin-top: 0.5rem;
    padding: 0.5rem 1.5rem;
  }
  .badges {
    position: fixed;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.2rem 0.55rem;
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 6px 0 0 0;
  }
  .version {
    position: relative;
    top: 0.1em;
    margin: 0;
    font-family: monospace;
    font-size: 0.9rem;
    font-weight: 500;
    color: #666;
  }
  .github-link {
    display: flex;
    color: #666;
  }
  .github-link:hover {
    color: #333;
  }
</style>
