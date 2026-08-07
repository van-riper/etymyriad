<script lang="ts">
  import '$lib/theme/variables.css';
  import { theme } from '$lib/theme/store.svelte';
  import Badges from '$lib/shared/Badges.svelte';
  import { Toaster } from 'svelte-sonner';

  let { children } = $props();

  $effect(() => {
    document.documentElement.dataset.theme = theme.resolved;
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

<!--
  Toaster mounts before the page content: its own onMount resets
  svelte-sonner's toast state, which would otherwise wipe out any
  toast a page fires during its own mount if Toaster mounted after it.
-->
<Toaster closeButton theme={theme.resolved} />

{@render children()}

<Badges />

<style>
  :global(html, body) {
    margin: 0;
    height: 100%;
    overflow: hidden;
  }

  /*
    Higher specificity than svelte-sonner's own
    [data-sonner-toaster][data-sonner-theme=...] rules, so these win
    regardless of stylesheet order.
  */
  :global(html) :global([data-sonner-toaster][data-sonner-theme='light']),
  :global(html) :global([data-sonner-toaster][data-sonner-theme='dark']) {
    --normal-bg: var(--bg-2);
    --normal-border: var(--ui-border);
    --normal-text: var(--tx);

    --success-bg: var(--bg-2);
    --success-border: var(--success);
    --success-text: var(--success);

    --info-bg: var(--bg-2);
    --info-border: var(--accent);
    --info-text: var(--accent);

    --warning-bg: var(--bg-2);
    --warning-border: var(--warning);
    --warning-text: var(--warning);

    --error-bg: var(--bg-2);
    --error-border: var(--danger);
    --error-text: var(--danger);
  }
</style>
