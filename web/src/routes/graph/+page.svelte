<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import GraphCanvas from '$lib/GraphCanvas.svelte';
  import { theme } from '$lib/theme.svelte';
  import SidePanel from '$lib/SidePanel.svelte';
  import type { Lexeme, ViewportTile } from '$lib/types';
  import { decodeViewportTile } from '$lib/binaryTile';
  import { cachedLexemeDetail } from '$lib/lexemeCache';
  import Badges from '$lib/Badges.svelte';

  const HOVER_DEBOUNCE_MS = 150;

  let lang = $state('');
  let headword = $state('');
  let error = $state<string | null>(null);
  let loading = $state(true);
  let graphCanvas: GraphCanvas = $state()!;
  let lastTile = $state<ViewportTile | null>(null);
  let nodeCount = $state(0);
  let loaded = $state(false);
  let hoverDetail = $state<Lexeme | null>(null);
  let hoverPos = $state<{ x: number; y: number } | null>(null);
  const lexemeCache = new Map<string, Lexeme>();
  let hoverGen = 0;
  let hoverTimer: ReturnType<typeof setTimeout> | undefined;

  async function fetchLexemeDetail(id: string): Promise<Lexeme | null> {
    const res = await fetch(`/api/lexeme/${encodeURIComponent(id)}`);
    if (!res.ok) return null;
    return await res.json();
  }

  async function handleClickNode(id: string) {
    const lexeme = await cachedLexemeDetail(
      lexemeCache,
      id,
      fetchLexemeDetail,
    );
    if (!lexeme) return;
    goto(
      resolve('/graph/[lang]/[headword]', {
        lang: lexeme.langCode,
        headword: lexeme.headword,
      }),
    );
  }

  function scheduleHover(node: string, x: number, y: number) {
    clearTimeout(hoverTimer);
    const gen = ++hoverGen;
    hoverTimer = setTimeout(async () => {
      const lexeme = await cachedLexemeDetail(
        lexemeCache,
        node,
        fetchLexemeDetail,
      );
      if (gen !== hoverGen || !lexeme) return;
      hoverDetail = lexeme;
      hoverPos = { x, y };
    }, HOVER_DEBOUNCE_MS);
  }

  function clearHover() {
    clearTimeout(hoverTimer);
    hoverGen++;
    hoverDetail = null;
    hoverPos = null;
  }

  onMount(async () => {
    loading = true;
    const res = await fetch('/api/graph/full');
    if (!res.ok) {
      error = 'Failed to load the whole-graph overview';
      loading = false;
      return;
    }
    const tile = decodeViewportTile(await res.arrayBuffer());
    lastTile = tile;
    nodeCount = tile.nodes.length;
    loaded = true;
    loading = false;
  });

  async function randomWord(randomLang: string) {
    const query = randomLang ? `?lang=${encodeURIComponent(randomLang)}` : '';
    const res = await fetch(`/api/random${query}`);
    if (!res.ok) return;
    const pick: { langCode: string; headword: string } = await res.json();
    goto(
      resolve('/graph/[lang]/[headword]', {
        lang: pick.langCode,
        headword: pick.headword,
      }),
    );
  }

  function search() {
    goto(resolve('/graph/[lang]/[headword]', { lang, headword }));
  }

  function centerView() {
    graphCanvas?.fitView();
  }

  onDestroy(() => {
    clearTimeout(hoverTimer);
  });
</script>

<svelte:head>
  <title>Etymyriad — whole graph</title>
  <meta
    name="description"
    content="A zoomed-out view of the entire etymology graph."
  />
</svelte:head>

<main>
  <SidePanel
    bind:lang
    bind:headword
    {nodeCount}
    focusDetail={null}
    {loading}
    onsearch={search}
    onrandom={randomWord}
  />

  <div class="content">
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}

    <div class="canvas-wrapper">
      {#if lastTile}
        <GraphCanvas
          tile={lastTile}
          focusId={null}
          theme={theme.resolved}
          onnodeclick={handleClickNode}
          onnodehover={scheduleHover}
          onhoverend={clearHover}
          bind:this={graphCanvas}
        />
      {/if}
      {#if loading}
        <p class="canvas-loading" role="status">Loading…</p>
      {/if}
      {#if loaded}
        <button
          class="center-button"
          aria-label="Center graph"
          title="Center graph"
          onclick={centerView}
        >
          <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
            <circle cx="10" cy="10" r="3" fill="currentColor" />
            <path
              stroke="currentColor"
              stroke-width="1.5"
              d="M10 1v4M10 15v4M1 10h4M15 10h4"
            />
          </svg>
        </button>
      {/if}
      {#if hoverDetail && hoverPos}
        <div
          class="hover-tooltip"
          style="left: {hoverPos.x}px; top: {hoverPos.y}px;"
        >
          <strong>{hoverDetail.headword}</strong> ({hoverDetail.langCode})
          {#if hoverDetail.senses[0]?.gloss}
            <div class="hover-gloss">{hoverDetail.senses[0].gloss}</div>
          {/if}
        </div>
      {/if}
    </div>
  </div>

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
    flex-direction: row;
    height: 100vh;
    background: var(--bg);
    color: var(--tx);
    font-family: system-ui, sans-serif;
  }
  .content {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
  }
  .error {
    margin: 1rem;
    padding: 0.5rem 0.75rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 6px;
    font-size: 0.9rem;
    color: var(--danger);
    border-color: var(--danger);
  }
  .canvas-wrapper {
    position: relative;
    flex: 1;
    min-height: 0;
  }
  .canvas-loading {
    position: absolute;
    top: 0.75rem;
    left: 0.75rem;
    margin: 0;
    padding: 0.25rem 0.6rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 6px;
    color: var(--tx-2);
    font-size: 0.85rem;
  }
  .center-button {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    padding: 0;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 6px;
    color: var(--tx-2);
    cursor: pointer;
  }
  .center-button:hover {
    color: var(--tx);
  }
  .hover-tooltip {
    position: absolute;
    pointer-events: none;
    transform: translate(8px, 8px);
    background: var(--bg);
    border: 1px solid var(--ui-border);
    padding: 0.25rem 0.5rem;
    font-size: 0.85rem;
    max-width: 16rem;
  }
  .hover-gloss {
    color: var(--tx-2);
  }
</style>
