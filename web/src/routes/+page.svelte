<script lang="ts">
  import { goto } from '$app/navigation';
  import { navigating } from '$app/state';
  import TreeShell from '$lib/components/TreeShell.svelte';
  import { treeUrl } from '$lib/utils/treeUrl';
  import { apiFetch } from '$lib/utils/apiFetch';

  let lang = $state('en');
  let headword = $state('etymology');
  const loading = $derived(!!navigating.to);

  function search() {
    goto(treeUrl(lang, headword));
  }

  async function randomWord(randomLang: string) {
    const query = randomLang ? `?lang=${encodeURIComponent(randomLang)}` : '';
    const res = await apiFetch(`/api/lexemes/random${query}`);
    if (!res.ok) return;
    const pick: { langCode: string; headword: string } = await res.json();
    goto(treeUrl(pick.langCode, pick.headword));
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
