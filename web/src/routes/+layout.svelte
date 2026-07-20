<script lang="ts">
  import '$lib/theme.css';
  import { theme } from '$lib/theme.svelte';

  let { children } = $props();

  $effect(() => {
    document.documentElement.dataset.theme = theme.resolved;
  });
</script>

{@render children()}
