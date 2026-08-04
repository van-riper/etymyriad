<!-- web/src/lib/ThemeToggle.svelte -->
<script lang="ts">
  import { theme } from '../theme.svelte';

  const LABELS = { light: 'Light', dark: 'Dark', system: 'Auto' } as const;
</script>

<button
  class="theme-toggle"
  type="button"
  onclick={() => theme.cycle()}
  aria-label={`Theme: ${LABELS[theme.mode]} (currently ${theme.resolved})`}
>
  {LABELS[theme.mode]}
</button>

<style>
  .theme-toggle {
    padding: 0.4rem 0.9rem;
    border: 1px solid var(--ui-border);
    border-radius: 999px;
    background: var(--bg-2);
    color: var(--tx);
    font-family: inherit;
    font-size: 0.9rem;
    cursor: pointer;
  }
  .theme-toggle:hover {
    border-color: var(--tx-3);
  }
</style>
