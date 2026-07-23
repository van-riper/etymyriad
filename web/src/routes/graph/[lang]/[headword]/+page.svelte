<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import type Sigma from 'sigma';
  import { buildGraph, canvasColors } from '$lib/graph';
  import { theme } from '$lib/theme.svelte';
  import SidePanel from '$lib/SidePanel.svelte';
  import type { Lexeme, ViewportTile } from '$lib/types';
  import { decodeViewportTile } from '$lib/binaryTile';
  import { cachedLexemeDetail } from '$lib/lexemeCache';
  import Badges from '$lib/Badges.svelte';

  // ponytail: fixed neighborhood box around the searched word. DrL's
  // real layout spans roughly +-1100 (see ETYM-69's resolution notes);
  // tune this once live pan/zoom-triggered refetching lands.
  const BOX_HALF_WIDTH = 300;

  // Debounce for hover-triggered detail fetches: fast mouse movement
  // across many nodes shouldn't fire one request per node passed over.
  const HOVER_DEBOUNCE_MS = 150;

  let lang = $state(page.params.lang as string);
  let headword = $state(page.params.headword as string);
  let error = $state<string | null>(null);
  let container: HTMLDivElement = $state()!;
  let renderer: Sigma | null = null;
  let lastTile: ViewportTile | null = null;
  let lastFocusId: string | null = null;
  let hoverDetail = $state<Lexeme | null>(null);
  let hoverPos = $state<{ x: number; y: number } | null>(null);
  let focusDetail = $state<Lexeme | null>(null);
  let nodeCount = $state(0);
  // Shared by hover and click so hovering then clicking the same
  // node doesn't fetch /api/lexeme/:id twice.
  const lexemeCache = new Map<string, Lexeme>();
  // Monotonic guards, not reactive state: let a stale in-flight call
  // detect it's been superseded before it touches shared state, so two
  // overlapping calls (a render, or a hover) can't clobber each other.
  let renderGen = 0;
  let hoverGen = 0;
  let loadGen = 0;
  let hoverTimer: ReturnType<typeof setTimeout> | undefined;

  async function loadNetwork(currentLang: string, currentHeadword: string) {
    const gen = ++loadGen;
    error = null;
    const posRes = await fetch(
      `/api/position/${encodeURIComponent(currentLang)}/${encodeURIComponent(currentHeadword)}`,
    );
    if (gen !== loadGen) return;

    renderer?.kill();
    renderer = null;

    if (!posRes.ok) {
      error = `No lexeme found for ${currentLang}:${currentHeadword}`;
      lastTile = null;
      lastFocusId = null;
      nodeCount = 0;
      focusDetail = null;
      return;
    }

    const position: { id: string; x: number; y: number } = await posRes.json();
    const [tileRes, detail] = await Promise.all([
      fetch(
        `/api/viewport?minX=${position.x - BOX_HALF_WIDTH}&minY=${position.y - BOX_HALF_WIDTH}` +
          `&maxX=${position.x + BOX_HALF_WIDTH}&maxY=${position.y + BOX_HALF_WIDTH}`,
      ),
      cachedLexemeDetail(lexemeCache, position.id, fetchLexemeDetail),
    ]);
    if (gen !== loadGen) return;

    if (!tileRes.ok) {
      error = `Failed to load the graph for ${currentLang}:${currentHeadword}`;
      lastTile = null;
      lastFocusId = null;
      nodeCount = 0;
      focusDetail = null;
      return;
    }

    const tile = decodeViewportTile(await tileRes.arrayBuffer());
    if (gen !== loadGen) return;
    lastTile = tile;
    lastFocusId = position.id;
    nodeCount = tile.nodes.length;
    focusDetail = detail;
    await renderNetwork(tile, position.id, currentLang, currentHeadword);
  }

  // Sigma needs WebGL, which only exists in the browser -- a static
  // import would crash SvelteKit's SSR render of this page, so load it
  // lazily here. Split out from loadNetwork so a theme change can
  // rebuild the renderer from the cached tile without re-fetching.
  async function renderNetwork(
    tile: ViewportTile,
    focusId: string,
    currentLang: string,
    currentHeadword: string,
  ) {
    const gen = ++renderGen;
    renderer?.kill();
    renderer = null;
    const { default: Sigma } = await import('sigma');
    if (gen !== renderGen) return;
    const colors = canvasColors(theme.resolved);
    const graph = buildGraph(tile, focusId, theme.resolved);
    renderer = new Sigma(graph, container, {
      defaultEdgeColor: colors.edge,
      labelColor: { color: colors.label },
    });

    renderer.on('clickNode', ({ node }) => {
      void handleClickNode(node, currentLang, currentHeadword);
    });
    renderer.on('enterNode', ({ node, event }) => {
      scheduleHover(node, event.x, event.y);
    });
    renderer.on('leaveNode', () => {
      clearHover();
    });
    // Masks the resize's ~70-110ms main-thread block (see onMount)
    // behind the opacity fade -- compositor-driven, so it stays smooth.
    renderer.on('afterRender', () => {
      container.style.opacity = '1';
    });
  }

  async function fetchLexemeDetail(id: string): Promise<Lexeme | null> {
    const res = await fetch(`/api/lexeme/${encodeURIComponent(id)}`);
    if (!res.ok) return null;
    return await res.json();
  }

  async function handleClickNode(
    node: string,
    currentLang: string,
    currentHeadword: string,
  ) {
    if (node === lastFocusId) return;
    const lexeme = await cachedLexemeDetail(
      lexemeCache,
      node,
      fetchLexemeDetail,
    );
    if (!lexeme) return;
    if (
      lexeme.langCode === currentLang &&
      lexeme.headword === currentHeadword
    ) {
      return;
    }
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

  // The route params are the single source of truth for what's rendered.
  // The form fields below are just an editable draft the user can type
  // into before submitting, so this effect ignores their local state and
  // only reacts to navigation (search submit, node click, random word).
  $effect(() => {
    lang = page.params.lang as string;
    headword = page.params.headword as string;
    loadNetwork(page.params.lang as string, page.params.headword as string);
  });

  $effect(() => {
    // Synchronously read theme.resolved so this effect re-tracks it as a
    // dependency -- renderNetwork's own reads of it happen after an
    // `await`, too late for Svelte's effect-tracking window. Rebuilding
    // from the cached tile avoids a redundant re-fetch.
    void theme.resolved;
    if (lastTile && lastFocusId) {
      renderNetwork(lastTile, lastFocusId, lang, headword);
    }
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
    renderer?.getCamera().animatedReset();
  }

  // Sigma only resizes on the window's `resize` event, so the side
  // panel collapsing/expanding (a pure CSS layout change) leaves it
  // rendered at the stale size, visually shifted. scheduleRender (not
  // scheduleRefresh) since no graph data changed -- just a redraw.
  onMount(() => {
    const observer = new ResizeObserver(() => {
      if (!renderer) return;
      container.style.opacity = '0';
      renderer.scheduleRender();
    });
    observer.observe(container);
    return () => observer.disconnect();
  });

  onDestroy(() => {
    renderer?.kill();
    clearTimeout(hoverTimer);
  });
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
  <SidePanel
    bind:lang
    bind:headword
    {nodeCount}
    {focusDetail}
    onsearch={search}
    onrandom={randomWord}
  />

  <div class="content">
    {#if error}
      <p class="error">{error}</p>
    {/if}

    <div class="canvas-wrapper">
      <div class="canvas" bind:this={container}></div>
      <button
        class="center-button"
        aria-label="Center graph"
        title="Center graph"
        onclick={centerView}
      >
        <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
          <circle
            cx="10"
            cy="10"
            r="3"
            fill="currentColor"
          />
          <path
            stroke="currentColor"
            stroke-width="1.5"
            d="M10 1v4M10 15v4M1 10h4M15 10h4"
          />
        </svg>
      </button>
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
    padding: 0 1rem;
    color: var(--danger);
  }
  .canvas-wrapper {
    position: relative;
    flex: 1;
  }
  .canvas {
    width: 100%;
    height: 100%;
    background: var(--bg);
    transition: opacity 120ms ease;
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
