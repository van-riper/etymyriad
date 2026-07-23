<script lang="ts">
  import { onDestroy } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
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
  let randomLang = $state('');
  let error = $state<string | null>(null);
  let container: HTMLDivElement = $state()!;
  let renderer: Sigma | null = null;
  let lastTile: ViewportTile | null = null;
  let lastFocusId: string | null = null;
  let hoverDetail = $state<Lexeme | null>(null);
  let hoverPos = $state<{ x: number; y: number } | null>(null);
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
      return;
    }

    const position: { id: string; x: number; y: number } = await posRes.json();
    const tileRes = await fetch(
      `/api/viewport?minX=${position.x - BOX_HALF_WIDTH}&minY=${position.y - BOX_HALF_WIDTH}` +
        `&maxX=${position.x + BOX_HALF_WIDTH}&maxY=${position.y + BOX_HALF_WIDTH}`,
    );
    if (gen !== loadGen) return;

    if (!tileRes.ok) {
      error = `Failed to load the graph for ${currentLang}:${currentHeadword}`;
      lastTile = null;
      lastFocusId = null;
      nodeCount = 0;
      return;
    }

    const tile = decodeViewportTile(await tileRes.arrayBuffer());
    if (gen !== loadGen) return;
    lastTile = tile;
    lastFocusId = position.id;
    nodeCount = tile.nodes.length;
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
      `/graph/${encodeURIComponent(lexeme.langCode)}/${encodeURIComponent(lexeme.headword)}`,
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
    bind:randomLang
    {nodeCount}
    onsearch={search}
    onrandom={randomWord}
  />

  <div class="content">
    {#if error}
      <p class="error">{error}</p>
    {/if}

    <div class="canvas-wrapper">
      <div class="canvas" bind:this={container}></div>
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
    border-top: 1px solid var(--ui-border);
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
