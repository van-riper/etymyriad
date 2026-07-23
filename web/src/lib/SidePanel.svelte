<!-- web/src/lib/SidePanel.svelte -->
<script lang="ts">
  import ThemeToggle from './ThemeToggle.svelte';

  let {
    lang = $bindable(),
    headword = $bindable(),
    randomLang = $bindable(),
    nodeCount,
    onsearch,
    onrandom,
  }: {
    lang: string;
    headword: string;
    randomLang: string;
    nodeCount: number;
    onsearch: () => void;
    onrandom: () => void;
  } = $props();

  let collapsed = $state(false);
  let keepLangCode = $state(false);

  function handleRandomClick() {
    randomLang = keepLangCode ? lang : '';
    onrandom();
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
        onsearch();
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
      <input
        class="lang-input"
        aria-label="Language code"
        bind:value={lang}
        placeholder="en"
      />
      <div class="random-group">
        <button type="button" onclick={handleRandomClick}>Random</button>
        <label class="muted-control">
          <input type="checkbox" bind:checked={keepLangCode} />
          Keep lang code
        </label>
      </div>
    </div>
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
  .lang-input {
    width: 6ch;
    max-width: 100%;
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
</style>
