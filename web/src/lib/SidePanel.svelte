<!-- web/src/lib/SidePanel.svelte -->
<script lang="ts">
  import ThemeToggle from './ThemeToggle.svelte';
  import LanguageCombobox from './LanguageCombobox.svelte';
  import type { Lexeme } from './types';
  import { wiktionaryUrl } from './wiktionary';
  import { langCodeError } from './validation';

  let {
    lang = $bindable(),
    headword = $bindable(),
    randomLang = $bindable(),
    nodeCount,
    focusDetail,
    onsearch,
    onrandom,
  }: {
    lang: string;
    headword: string;
    randomLang: string;
    nodeCount: number;
    focusDetail: Lexeme | null;
    onsearch: () => void;
    onrandom: () => void;
  } = $props();

  let collapsed = $state(false);
  let keepLangCode = $state(false);
  let error = $state<string | null>(null);

  function handleRandomClick() {
    error = null;
    randomLang = keepLangCode ? lang : '';
    onrandom();
  }

  function handleSearch() {
    error = langCodeError(lang);
    if (error) return;
    onsearch();
  }
</script>

<div class="side-panel" class:collapsed>
  <div class="header-row">
    <button
      class="collapse-toggle"
      type="button"
      onclick={() => (collapsed = !collapsed)}
      aria-label={collapsed ? 'Expand panel' : 'Collapse panel'}
      aria-expanded={!collapsed}
    >
      {collapsed ? '»' : '«'}
    </button>
    {#if !collapsed}
      <h1>Etymyriad</h1>
    {/if}
  </div>
  {#if !collapsed}
    <form
      class="search-row"
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
      />
      <button type="submit">Search</button>
    </form>
    <div class="lang-row">
      <LanguageCombobox bind:value={lang} placeholder="en" />
      <div class="random-group">
        <button type="button" onclick={handleRandomClick}>Random</button>
        <label class="muted-control">
          <input type="checkbox" bind:checked={keepLangCode} />
          Keep lang code
        </label>
      </div>
    </div>
    {#if error}
      <p class="lang-error">{error}</p>
    {/if}
    {#if focusDetail}
      <div class="detail">
        <h2 class="detail-headword">
          {focusDetail.headword}
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
          rel="noreferrer"
        >
          View on Wiktionary
        </a>
      </div>
    {/if}
    <div class="footer-row">
      <span class="muted-control">
        Color:
        <ThemeToggle />
      </span>
      <span class="muted-control">N = {nodeCount}</span>
    </div>
  {/if}
</div>

<style>
  .side-panel {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1rem;
    width: max-content;
    max-width: 90vw;
    overflow-y: auto;
    border-right: 1px solid var(--ui-border);
  }
  .side-panel.collapsed {
    padding: 1rem 0.5rem;
  }
  .header-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .collapse-toggle {
    font-family: inherit;
    font-size: 1rem;
    border: 1px solid var(--ui-border);
    background: var(--bg-2);
    color: var(--tx);
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
    cursor: pointer;
  }
  h1 {
    flex: 1;
    margin: 0;
    text-align: center;
    font-family: 'Libre Baskerville', serif;
    font-weight: 700;
    font-size: 1.5rem;
    letter-spacing: 0.05em;
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
  .search-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }
  .lang-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.5rem;
  }
  .random-group {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.3rem;
  }
  .lang-error {
    margin: 0;
    font-size: 0.9rem;
    color: var(--danger);
  }
  .footer-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: auto;
  }
  .muted-control {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--tx-2);
    font-size: 0.9rem;
  }
  .detail {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--ui-border);
    max-width: 16rem;
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
</style>
