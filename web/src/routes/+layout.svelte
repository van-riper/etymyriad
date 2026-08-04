<script lang="ts">
  import '$lib/theme.css';
  import { theme } from '$lib/theme.svelte';
  import Badges from '$lib/Badges.svelte';

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

{@render children()}

<Badges />

<style>
  :global(html, body) {
    margin: 0;
    height: 100%;
    overflow: hidden;
  }
</style>
