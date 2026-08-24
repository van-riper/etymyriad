<!-- web/src/lib/components/TreeShell.svelte -->
<script lang="ts">
  import { Popover } from 'bits-ui';
  import ThemeToggle from '../theme/ThemeToggle.svelte';
  import LanguageCombobox from '../language/LanguageCombobox.svelte';
  import TreeDiagram from './TreeDiagram.svelte';
  import type {
    Lexeme,
    LexemeSummary,
    TreeNode,
    TreeSlice,
  } from '../shared/types';
  import { wiktionaryUrl } from './wiktionary';
  import { displayHeadword } from './headword';
  import { headwordError, langCodeError } from '../shared/validation';
  import {
    DEFAULT_HEADWORD,
    DEFAULT_LANG,
    DEFAULT_TREE_SLICE,
  } from './defaultTree';

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
    onnodedblclick,
    onpickcandidate,
    onhomographescape,
    ondetailescape,
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
    onnodedblclick?: (node: TreeNode) => void;
    onpickcandidate?: (etymKey: string) => void;
    onhomographescape?: () => void;
    ondetailescape?: () => void;
  } = $props();

  let keepLangCode = $state(false);
  let error = $state<string | null>(null);
  let showLegend = $state(false);
  // Set once the empty-state landing card has been submitted, so the
  // search bar's CSS transition (its shrink-into-docked-bar animation)
  // has time to play before onsearch actually navigates away.
  let leaving = $state(false);
  const LANDING_TRANSITION_MS = 350;

  // A nav that resolves fast (the common case, off a local Postgres)
  // shouldn't flash a loading indicator -- only show one once loading
  // has run long enough to be worth mentioning.
  const SPINNER_DELAY_MS = 300;
  let showSpinner = $state(false);
  $effect(() => {
    if (!loading) {
      showSpinner = false;
      return;
    }
    const timer = setTimeout(() => {
      showSpinner = true;
    }, SPINNER_DELAY_MS);
    return () => clearTimeout(timer);
  });

  function handleSearch() {
    if (status === 'empty') {
      if (!headword.trim()) headword = DEFAULT_HEADWORD;
      if (!lang.trim()) lang = DEFAULT_LANG;
    }
    error = headwordError(headword) ?? langCodeError(lang);
    if (error) return;
    if (status === 'empty') {
      leaving = true;
      setTimeout(onsearch, LANDING_TRANSITION_MS);
      return;
    }
    onsearch();
  }

  function handleRandomClick() {
    error = null;
    onrandom(keepLangCode ? lang.trim() || DEFAULT_LANG : '');
  }
</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key !== 'Escape') return;
    if (status === 'homograph') onhomographescape?.();
    if (status === 'tree' && focusDetail) ondetailescape?.();
  }}
/>

<div class="shell">
  <Popover.Root bind:open={showLegend}>
    <div class="canvas" class:canvas--empty={status === 'empty'}>
      {#if status === 'tree' && slice}
        <TreeDiagram
          {slice}
          onnodeclick={onnodeclick ?? (() => {})}
          onnodedblclick={onnodedblclick ?? (() => {})}
        />
      {:else if status === 'empty'}
        <div class="preview-tree" aria-hidden="true" inert>
          <TreeDiagram
            slice={DEFAULT_TREE_SLICE}
            onnodeclick={() => {}}
            onnodedblclick={() => {}}
          />
        </div>
      {/if}
    </div>

    <div
      class="search-bar"
      class:search-bar--landing={status === 'empty' && !leaving}
    >
      {#if status === 'empty'}
        <div class="landing-copy">
          <h1>Etymyriad</h1>
          <p class="author">By: Finn van Riper</p>
          <p class="lead">
            Every word has a documented history. Etymyriad traces it, one
            sourced link at a time.
          </p>
          <p class="lead">
            Follow any word back through its ancestors, branch into its
            cognates, or explore its descendants across languages. The tree
            below, for the English word etymology, is a live example already on
            screen.
          </p>
        </div>
      {/if}
      <div class="search-bar-controls">
        <Popover.Trigger class="icon-button" aria-label="Legend" title="Legend">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <circle
              cx="12"
              cy="12"
              r="9"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            />
            <circle cx="12" cy="8" r="1" fill="currentColor" />
            <line
              x1="12"
              y1="11"
              x2="12"
              y2="16"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
          </svg>
        </Popover.Trigger>
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
            placeholder={DEFAULT_HEADWORD}
            disabled={loading || leaving}
          />
          <LanguageCombobox bind:value={lang} placeholder={DEFAULT_LANG} />
          <button
            type="submit"
            class="icon-button"
            disabled={loading || leaving}
            aria-label={status === 'empty' ? 'Explore' : 'Search'}
            title={status === 'empty' ? 'Explore' : 'Search'}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <circle
                cx="10"
                cy="10"
                r="7"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              />
              <line
                x1="15"
                y1="15"
                x2="21"
                y2="21"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
              />
            </svg>
          </button>
        </form>
        <button
          type="button"
          class="icon-button"
          onclick={handleRandomClick}
          disabled={loading || leaving}
          aria-label="Random"
          title="Random"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <rect
              x="2"
              y="2"
              width="20"
              height="20"
              rx="4"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            />
            <circle cx="7" cy="7" r="1.6" fill="currentColor" />
            <circle cx="17" cy="7" r="1.6" fill="currentColor" />
            <circle cx="12" cy="12" r="1.6" fill="currentColor" />
            <circle cx="7" cy="17" r="1.6" fill="currentColor" />
            <circle cx="17" cy="17" r="1.6" fill="currentColor" />
          </svg>
        </button>
        <label class="muted-control">
          <input type="checkbox" bind:checked={keepLangCode} />
          Keep lang code
        </label>
        <ThemeToggle />
        {#if showSpinner}
          <span class="loading-spinner" role="status" aria-label="Loading"
          ></span>
        {/if}
      </div>
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
          {#if focusDetail.isRedlink}
            <span class="detail-tag">redlink</span>
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

    <Popover.ContentStatic class="legend-card">
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
    </Popover.ContentStatic>
  </Popover.Root>
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
  .canvas--empty {
    /* the empty state's search bar overlays the whole canvas (it's
       centered, not docked), so the tree behind it can fill it too. */
    padding-top: 0;
  }
  .preview-tree {
    position: absolute;
    inset: 0;
    filter: blur(6px);
    opacity: 0.35;
    pointer-events: none;
  }
  .landing-copy {
    max-width: 32rem;
    text-align: center;
    overflow: hidden;
    transition:
      opacity 200ms ease,
      max-height 350ms ease,
      margin 350ms ease;
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
  .icon-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
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
    transition:
      top 350ms ease,
      transform 350ms ease,
      padding 350ms ease,
      gap 350ms ease,
      max-width 350ms ease,
      border-radius 350ms ease;
  }
  .search-bar--landing {
    top: 50%;
    transform: translate(-50%, -50%);
    flex-direction: column;
    padding: 2.5rem 2rem;
    gap: 1.5rem;
    max-width: min(90vw, 34rem);
    border-radius: 16px;
  }
  .search-bar:not(.search-bar--landing) .landing-copy {
    opacity: 0;
    max-height: 0;
    margin: 0;
    pointer-events: none;
  }
  .search-bar-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
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
  .loading-spinner {
    display: inline-block;
    width: 1rem;
    height: 1rem;
    border: 2px solid var(--ui-border);
    border-top-color: var(--tx-2);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
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
  :global(.legend-card) {
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
    border-top: 1px solid var(--tx-3);
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
