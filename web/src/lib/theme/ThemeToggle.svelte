<!-- web/src/lib/ThemeToggle.svelte -->
<script lang="ts">
  import { theme } from './store.svelte';

  const LABELS = { light: 'Light', dark: 'Dark', system: 'Auto' } as const;
</script>

<button
  class="theme-toggle"
  type="button"
  onclick={() => theme.cycle()}
  aria-label={`Theme: ${LABELS[theme.mode]} (currently ${theme.resolved})`}
>
  {#if theme.mode === 'light'}
    <svg
      data-testid="icon-sun"
      viewBox="0 0 24 24"
      width="24"
      height="24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4.5" />
      <path
        d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"
      />
    </svg>
  {:else if theme.mode === 'dark'}
    <svg
      data-testid="icon-moon"
      viewBox="0 0 24 24"
      width="24"
      height="24"
      aria-hidden="true"
    >
      <mask id="theme-toggle-moon-mask">
        <rect x="0" y="0" width="24" height="24" fill="white" />
        <circle cx="15.5" cy="8.5" r="6.5" fill="black" />
      </mask>
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="currentColor"
        mask="url(#theme-toggle-moon-mask)"
      />
    </svg>
  {:else}
    <svg
      data-testid="icon-auto"
      viewBox="0 0 24 24"
      width="24"
      height="24"
      aria-hidden="true"
    >
      <mask id="theme-toggle-auto-mask">
        <rect x="0" y="0" width="24" height="24" fill="white" />
        <circle cx="12" cy="12" r="4.4" fill="black" />
      </mask>
      <path
        d="M12 3A9 9 0 0 1 12 21Z"
        fill="currentColor"
        mask="url(#theme-toggle-auto-mask)"
      />
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="currentColor"
        stroke-width="2.4"
      />
      <path d="M12 8.4A3.6 3.6 0 0 0 12 15.6Z" fill="currentColor" />
    </svg>
  {/if}
</button>

<style>
  .theme-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.3rem;
    border: 1px solid var(--ui-border);
    border-radius: 999px;
    background: var(--bg-2);
    color: var(--tx);
    cursor: pointer;
  }
  .theme-toggle:hover {
    border-color: var(--tx-3);
  }
</style>
