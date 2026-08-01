<script lang="ts">
  import { onDestroy } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import GraphCanvas from '$lib/GraphCanvas.svelte';
  import { theme } from '$lib/theme.svelte';
  import SidePanel from '$lib/SidePanel.svelte';
  import type { Lexeme, ViewportTile } from '$lib/types';
  import { decodeViewportTile } from '$lib/binaryTile';
  import { buildGraph } from '$lib/graph';
  import { cachedLexemeDetail } from '$lib/lexemeCache';
  import Badges from '$lib/Badges.svelte';
  import type { HomographCandidate, PositionResult } from '$lib/types';

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
  let loading = $state(false);
  let graphCanvas: GraphCanvas = $state()!;
  let lastTile = $state<ViewportTile | null>(null);
  let lastFocusId = $state<string | null>(null);
  let graphData = $derived(
    lastTile && buildGraph(lastTile, lastFocusId, theme.resolved),
  );
  let hoverDetail = $state<Lexeme | null>(null);
  let hoverPos = $state<{ x: number; y: number } | null>(null);
  let focusDetail = $state<Lexeme | null>(null);
  let nodeCount = $state(0);
  // True when the searched word resolved but none of its etymology
  // edges land inside this fixed-size viewport box -- e.g. a distant
  // ancestor/descendant DrL placed far away spatially. A real but rare
  // case: /api/viewport is a pure bounding-box query, not a graph
  // traversal, so a word's edges can exist without appearing in its
  // own tile. Distinct from `error`, which means the word itself
  // couldn't be found.
  let isEmpty = $state(false);
  // True only once a tile has actually rendered -- gates UI (e.g. the
  // center-graph button) that only makes sense once there's a graph on
  // screen to act on, not during loading/error/empty/candidate-picker.
  let loaded = $state(false);
  // Set when lang+headword has more than one etym_key (a homograph)
  // and the URL doesn't say which one -- see ETYM-75. Non-null means
  // the canvas shows a picker instead of a graph. candidateLang/
  // candidateHeadword snapshot the word the picker is *for*,
  // separate from lang/headword -- those two are the live search-box
  // draft (see the effect below) and would otherwise make the picker's
  // heading change while the user is still typing the next search.
  let candidates = $state<HomographCandidate[] | null>(null);
  let candidateLang = $state('');
  let candidateHeadword = $state('');
  // Shared by hover and click so hovering then clicking the same
  // node doesn't fetch /api/lexeme/:id twice.
  const lexemeCache = new Map<string, Lexeme>();
  // Monotonic guards, not reactive state: let a stale in-flight call
  // detect it's been superseded before it touches shared state, so two
  // overlapping calls (a render, or a hover) can't clobber each other.
  let loadGen = 0;
  let hoverGen = 0;
  let hoverTimer: ReturnType<typeof setTimeout> | undefined;

  async function loadNetwork(
    currentLang: string,
    currentHeadword: string,
    etymKey: string | null,
  ) {
    const gen = ++loadGen;
    error = null;
    candidates = null;
    isEmpty = false;
    loaded = false;
    loading = true;
    const query =
      etymKey !== null ? `?etym=${encodeURIComponent(etymKey)}` : '';
    const posRes = await fetch(
      `/api/position/${encodeURIComponent(currentLang)}/${encodeURIComponent(currentHeadword)}${query}`,
    );
    if (gen !== loadGen) return;

    if (!posRes.ok) {
      error = `No lexeme found for ${currentLang}:${currentHeadword}`;
      lastTile = null;
      lastFocusId = null;
      nodeCount = 0;
      focusDetail = null;
      loading = false;
      return;
    }

    const result: PositionResult = await posRes.json();
    if ('candidates' in result) {
      candidates = result.candidates;
      candidateLang = currentLang;
      candidateHeadword = currentHeadword;
      lastTile = null;
      lastFocusId = null;
      nodeCount = 0;
      focusDetail = null;
      loading = false;
      return;
    }
    const position = result;
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
      loading = false;
      return;
    }

    const tile = decodeViewportTile(await tileRes.arrayBuffer());
    if (gen !== loadGen) return;
    lastTile = tile;
    lastFocusId = position.id;
    nodeCount = tile.nodes.length;
    focusDetail = detail;
    isEmpty = !tile.edges.some(
      (e) => e.srcId === position.id || e.dstId === position.id,
    );
    loaded = !isEmpty;
    loading = false;
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
    loadNetwork(
      page.params.lang as string,
      page.params.headword as string,
      page.url.searchParams.get('etym'),
    );
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

  function pickCandidate(candidate: HomographCandidate) {
    goto(
      resolve(
        `/graph/[lang]/[headword]?etym=${encodeURIComponent(candidate.etymKey)}`,
        { lang: candidateLang, headword: candidateHeadword },
      ),
    );
  }

  function centerView() {
    graphCanvas?.fitView();
  }

  onDestroy(() => {
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
    {loading}
    onsearch={search}
    onrandom={randomWord}
  />

  <div class="content">
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}

    {#if isEmpty && !error}
      <p class="empty-notice" role="status">
        "{headword}" has no etymological connections in this view, its
        linked words may lie outside the visible area.
      </p>
    {/if}

    {#if candidates}
      <div class="homograph-picker">
        <p>
          "{candidateHeadword}" ({candidateLang}) has {candidates.length}
          distinct entries. Pick one:
        </p>
        <ul>
          {#each candidates as candidate (candidate.id)}
            <li>
              <button type="button" onclick={() => pickCandidate(candidate)}>
                {#if candidate.pos}<span class="candidate-pos"
                    >{candidate.pos}</span
                  >{/if}
                {candidate.gloss ?? '(no gloss)'}
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <div class="canvas-wrapper">
      {#if graphData}
        <GraphCanvas
          data={graphData}
          theme={theme.resolved}
          onnodeclick={(id) =>
            handleClickNode(
              id,
              page.params.lang as string,
              page.params.headword as string,
            )}
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
  .error,
  .empty-notice {
    margin: 1rem;
    padding: 0.5rem 0.75rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 6px;
    font-size: 0.9rem;
  }
  .error {
    color: var(--danger);
    border-color: var(--danger);
  }
  .empty-notice {
    color: var(--tx-2);
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
  .homograph-picker {
    padding: 1rem;
    overflow-y: auto;
  }
  .homograph-picker ul {
    list-style: none;
    margin: 0.5rem 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .homograph-picker button {
    width: 100%;
    text-align: left;
    padding: 0.5rem 0.75rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 6px;
    color: var(--tx);
    font-size: 0.95rem;
    cursor: pointer;
  }
  .homograph-picker button:hover {
    border-color: var(--tx-2);
  }
  .candidate-pos {
    color: var(--tx-2);
    font-style: italic;
    margin-right: 0.4rem;
  }
  .canvas-wrapper {
    position: relative;
    flex: 1;
    min-height: 0;
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
