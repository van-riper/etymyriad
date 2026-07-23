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
</script>

<div class="side-panel" class:collapsed>
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
    <span class="color-toggle">
      <span class="theme-label">Color:</span>
      <ThemeToggle />
    </span>
    <span class="node-count">N = {nodeCount}</span>
    <form
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
    <input
      class="lang-input"
      aria-label="Language code"
      bind:value={lang}
      placeholder="en"
    />
    <div class="random-row">
      <span class="random-lang-label">Language filter:</span>
      <input
        class="lang-input"
        aria-label="Random language filter"
        bind:value={randomLang}
        placeholder={lang || 'any'}
      />
      <button type="button" onclick={onrandom}>Random</button>
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
  .collapse-toggle {
    align-self: flex-start;
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
    margin: 0;
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
  form {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }
  .color-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .node-count,
  .theme-label {
    color: var(--tx-2);
  }
  .random-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }
  .random-lang-label {
    color: var(--tx-2);
  }
</style>
