<!-- web/src/lib/components/TreeShell.svelte -->
<script lang="ts">
  import ThemeToggle from './ThemeToggle.svelte';
  import LanguageCombobox from './LanguageCombobox.svelte';
  import TreeDiagram from './TreeDiagram.svelte';
  import type { Lexeme, LexemeSummary, TreeNode, TreeSlice } from '../types';
  import { wiktionaryUrl } from '../utils/wiktionary';
  import { displayHeadword } from '../utils/headword';
  import { headwordError, langCodeError } from '../utils/validation';

  let {
    lang = $bindable(),
    headword = $bindable(),
    status,
    queryLang = '',
    queryHeadword = '',
    slice = null,
    focusDetail = null,
    candidates = [],
    loading = false,
    onsearch,
    onrandom,
    onnodeclick,
    onpickcandidate,
  }: {
    lang: string;
    headword: string;
    status: 'empty' | 'notfound' | 'homograph' | 'tree';
    queryLang?: string;
    queryHeadword?: string;
    slice?: TreeSlice | null;
    focusDetail?: Lexeme | null;
    candidates?: LexemeSummary[];
    loading?: boolean;
    onsearch: () => void;
    onrandom: (lang: string) => void;
    onnodeclick?: (node: TreeNode) => void;
    onpickcandidate?: (etymKey: string) => void;
  } = $props();

  let keepLangCode = $state(false);
  let error = $state<string | null>(null);
  let showLegend = $state(false);

  function handleSearch() {
    error = headwordError(headword) ?? langCodeError(lang);
    if (error) return;
    onsearch();
  }

  function handleRandomClick() {
    error = null;
    onrandom(keepLangCode ? lang : '');
  }
</script>

<div class="shell">
  <div class="canvas">
    {#if status === 'tree' && slice}
      <TreeDiagram {slice} onnodeclick={onnodeclick ?? (() => {})} />
    {:else if status === 'empty'}
      <div class="landing-copy">
        <h1>Etymyriad</h1>
        <p class="author">By: Finn van Riper</p>
        <p class="lead">
          An interactive graph of words and their origins.
        </p>
        <p class="lead">
          Trace the etymology of any <i>lexeme</i> (word) in any language
          back through each <i>etymon</i> (word ancestor) that influenced
          it, and explore its cognates, derivatives, and roots!
        </p>
      </div>
    {/if}
  </div>

  <div class="search-bar">
    <button
      type="button"
      aria-expanded={showLegend}
      onclick={() => (showLegend = !showLegend)}
    >
      Legend
    </button>
    <form
      class="search-form"
      onsubmit={(e) => {
        e.preventDefault();
        handleSearch();
      }}
    >
      <input
        class="headword-input"
        aria-label="Headword"
        bind:value={headword}
        placeholder="etymology"
        disabled={loading}
      />
      <LanguageCombobox bind:value={lang} placeholder="en" />
      <button type="submit" disabled={loading}>Search</button>
    </form>
    <button type="button" onclick={handleRandomClick} disabled={loading}>
      Random
    </button>
    <label class="muted-control">
      <input type="checkbox" bind:checked={keepLangCode} />
      Keep lang code
    </label>
    <ThemeToggle />
    {#if loading}
      <p class="loading-indicator" role="status">Loading…</p>
    {/if}
    {#if error}
      <p class="lang-error">{error}</p>
    {/if}
  </div>

  {#if status === 'notfound'}
    <p class="error" role="alert">
      No matches for "{queryHeadword}" ({queryLang}).
    </p>
  {/if}

  {#if status === 'homograph'}
    <div class="homograph-picker">
      <p>
        "{queryHeadword}" ({queryLang}) has {candidates.length}
        distinct entries. Pick one:
      </p>
      <ul>
        {#each candidates as candidate (candidate.id)}
          <li>
            <button
              type="button"
              onclick={() => onpickcandidate?.(candidate.etymKey)}
            >
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

  {#if status === 'tree' && focusDetail}
    <div class="detail-card">
      <h2 class="detail-headword">
        {displayHeadword(focusDetail.headword, focusDetail.isReconstructed)}
        {#if focusDetail.isReconstructed}
          <span class="detail-tag">reconstructed</span>
        {/if}
      </h2>
      <p class="detail-lang">{focusDetail.langName}</p>
      {#if focusDetail.romanization}
        <p class="detail-romanization">{focusDetail.romanization}</p>
      {/if}
      <ul class="detail-senses">
        {#each focusDetail.senses as sense (sense.sourceRef + (sense.gloss ?? ''))}
          <li>
            {#if sense.pos}<span class="detail-pos">{sense.pos}</span>{/if}
            {sense.gloss ?? ''}
          </li>
        {/each}
      </ul>
      <a
        class="detail-link"
        href={wiktionaryUrl(focusDetail)}
        target="_blank"
        rel="noreferrer external"
      >
        View on Wiktionary
      </a>
    </div>
  {/if}

  {#if showLegend}
    <div class="legend-card">
      <h2 class="legend-title">Legend</h2>
      <ul class="legend-list">
        <li>
          <span class="legend-swatch line"></span>
          Ancestor/descendant link
        </li>
        <li>
          <span class="legend-swatch line cross-link"></span>
          Cross-link (a same-generation or extra relation)
        </li>
        <li>
          <span class="legend-swatch box overflow"></span>
          Collapsed siblings ("+N more")
        </li>
      </ul>
    </div>
  {/if}
</div>

<style>
  .shell {
    position: relative;
    height: 100vh;
    background: var(--bg);
    color: var(--tx);
    font-family: system-ui, sans-serif;
    overflow: hidden;
  }
  .canvas {
    position: absolute;
    inset: 0;
    /* ponytail: fixed clearance sized for the search bar's typical
       1-2 line height; swap for a measured (ResizeObserver) offset
       if the bar ever grows taller than this. */
    padding-top: 9rem;
    box-sizing: border-box;
  }
  .landing-copy {
    margin: auto;
    max-width: 32rem;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 0 1rem;
    text-align: center;
  }
  .landing-copy h1 {
    margin: 0;
    font-family: 'Libre Baskerville', serif;
    font-weight: 700;
    font-size: 2.5rem;
  }
  .author {
    margin: 0.5rem 0 0;
    font-size: 0.9rem;
    color: var(--tx-2);
  }
  .lead {
    margin-top: 1rem;
    line-height: 1.5;
  }
  input,
  button {
    font-family: inherit;
    font-size: 1rem;
  }
  .headword-input {
    width: 12rem;
    max-width: 100%;
  }
  .search-bar {
    position: absolute;
    top: 1rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 8px;
    max-width: calc(100vw - 2rem);
  }
  .search-form {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .muted-control {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--tx-2);
    font-size: 0.9rem;
  }
  .loading-indicator {
    margin: 0;
    font-size: 0.9rem;
    color: var(--tx-2);
  }
  .lang-error {
    margin: 0;
    font-size: 0.9rem;
    color: var(--danger);
  }
  .error {
    position: absolute;
    top: 5.5rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
    margin: 0;
    padding: 0.5rem 0.75rem;
    background: var(--bg-2);
    border: 1px solid var(--danger);
    border-radius: 6px;
    font-size: 0.9rem;
    color: var(--danger);
  }
  .homograph-picker {
    position: absolute;
    top: 5.5rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
    max-width: 24rem;
    max-height: calc(100vh - 7rem);
    overflow-y: auto;
    padding: 0.75rem 1rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 8px;
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
    background: var(--bg);
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
  .detail-card {
    position: absolute;
    top: 1rem;
    right: 1rem;
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    max-width: 16rem;
    max-height: calc(100vh - 2rem);
    overflow-y: auto;
    padding: 0.75rem 1rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 8px;
  }
  .detail-headword {
    margin: 0;
    font-size: 1.1rem;
  }
  .detail-tag {
    font-size: 0.75rem;
    font-weight: 400;
    color: var(--tx-2);
    border: 1px solid var(--ui-border);
    border-radius: 4px;
    padding: 0.05rem 0.3rem;
    margin-left: 0.3rem;
  }
  .detail-lang {
    margin: 0;
    color: var(--tx-2);
    font-size: 0.9rem;
  }
  .detail-romanization {
    margin: 0;
    font-style: italic;
    color: var(--tx-2);
  }
  .detail-senses {
    margin: 0;
    padding-left: 1.1rem;
    font-size: 0.9rem;
  }
  .detail-pos {
    color: var(--tx-2);
    font-style: italic;
    margin-right: 0.3rem;
  }
  .detail-link {
    font-size: 0.85rem;
    color: var(--tx-2);
  }
  .legend-card {
    position: absolute;
    bottom: 1rem;
    left: 1rem;
    z-index: 10;
    max-width: 16rem;
    padding: 0.75rem 1rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 8px;
  }
  .legend-title {
    margin: 0 0 0.4rem;
    font-size: 1rem;
  }
  .legend-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    font-size: 0.85rem;
  }
  .legend-list li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .legend-swatch {
    flex: none;
  }
  .legend-swatch.line {
    width: 1.5rem;
    height: 0;
    border-top: 1.5px solid var(--tx-2);
  }
  .legend-swatch.line.cross-link {
    border-top: 1.5px dashed var(--tx-3);
  }
  .legend-swatch.box {
    width: 1.1rem;
    height: 0.8rem;
    border-radius: 3px;
  }
  .legend-swatch.box.overflow {
    border: 1.5px dashed var(--tx-2);
  }
</style>
