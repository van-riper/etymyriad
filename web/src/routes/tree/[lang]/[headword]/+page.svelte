<script lang="ts">
  import { goto } from '$app/navigation';
  import { page, navigating } from '$app/state';
  import TreeShell from '$lib/components/TreeShell.svelte';
  import { treeUrl } from '$lib/utils/treeUrl';
  import type { TreeNode } from '$lib/types';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  let lang = $state(page.params.lang as string);
  let headword = $state(page.params.headword as string);
  const loading = $derived(!!navigating.to);

  // page.params is the source of truth for what's rendered; this just
  // keeps the search box's draft in sync after any navigation, without
  // overwriting what the user is mid-typing before they submit.
  $effect(() => {
    lang = page.params.lang as string;
    headword = page.params.headword as string;
  });

  function search() {
    goto(treeUrl(lang, headword));
  }

  async function randomWord(randomLang: string) {
    const query = randomLang ? `?lang=${encodeURIComponent(randomLang)}` : '';
    const res = await fetch(`/api/lexemes/random${query}`);
    if (!res.ok) return;
    const pick: { langCode: string; headword: string } = await res.json();
    goto(treeUrl(pick.langCode, pick.headword));
  }

  function handleNodeClick(node: TreeNode) {
    if (node.depth === 0) return;
    goto(treeUrl(node.langCode, node.headword));
  }

  function pickCandidate(etymKey: string) {
    goto(treeUrl(data.lang, data.headword, etymKey));
  }
</script>

<TreeShell
  bind:lang
  bind:headword
  status={data.status}
  queryLang={data.lang}
  queryHeadword={data.headword}
  slice={data.status === 'tree' ? data.slice : null}
  focusDetail={data.status === 'tree' ? data.focusDetail : null}
  candidates={data.status === 'homograph' ? data.candidates : []}
  {loading}
  onsearch={search}
  onrandom={randomWord}
  onnodeclick={handleNodeClick}
  onpickcandidate={pickCandidate}
/>
