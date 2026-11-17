<script lang="ts">
  import { goto } from '$app/navigation';
  import { navigating } from '$app/state';
  import TreeShell from '#lib/tree/TreeShell.svelte';
  import { treeUrl } from '#lib/tree/url.js';
  import { apiFetch } from '#lib/shared/apiFetch.js';

  let lang = $state('');
  let headword = $state('');
  let fetchingRandom = $state(false);
  const loading = $derived(!!navigating.to || fetchingRandom);

  function search() {
    goto(treeUrl(lang, headword));
  }

  async function randomWord(randomLang: string) {
    if (fetchingRandom) return;
    fetchingRandom = true;
    try {
      const query = randomLang ? `?lang=${encodeURIComponent(randomLang)}` : '';
      const res = await apiFetch(`/api/terms/random${query}`);
      if (!res.ok) return;
      const pick: { langCode: string; headword: string } = await res.json();
      goto(treeUrl(pick.langCode, pick.headword));
    } finally {
      fetchingRandom = false;
    }
  }
</script>

<TreeShell
  bind:lang
  bind:headword
  status="empty"
  {loading}
  onsearch={search}
  onrandom={randomWord}
/>
