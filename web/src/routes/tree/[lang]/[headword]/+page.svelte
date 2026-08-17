<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { page, navigating } from '$app/state';
  import TreeShell from '$lib/tree/TreeShell.svelte';
  import { treeUrl } from '$lib/tree/url';
  import { cachedLexemeDetail } from '$lib/tree/lexemeCache';
  import { apiFetch } from '$lib/shared/apiFetch';
  import type { Lexeme, TreeNode } from '$lib/shared/types';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  let lang = $state(page.params.lang as string);
  let headword = $state(page.params.headword as string);
  const loading = $derived(!!navigating.to);

  // Detail for the last single-clicked node, shown in the detail
  // panel in place of the focus word's own detail. Reset on
  // navigation so the new focus word's detail takes back over.
  let clickedDetail = $state<Lexeme | null>(null);
  const lexemeCache = new Map<string, Lexeme>();
  const detail = $derived(
    clickedDetail ?? (data.status === 'tree' ? data.focusDetail : null),
  );

  // page.params is the source of truth for what's rendered; this just
  // keeps the search box's draft in sync after any navigation, without
  // overwriting what the user is mid-typing before they submit.
  $effect(() => {
    lang = page.params.lang as string;
    headword = page.params.headword as string;
    clickedDetail = null;
  });

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

  async function fetchLexemeDetail(id: string): Promise<Lexeme | null> {
    const res = await apiFetch(`/api/lexemes/${encodeURIComponent(id)}`);
    if (!res.ok) return null;
    return await res.json();
  }

  async function handleNodeClick(node: TreeNode) {
    clickedDetail = await cachedLexemeDetail(
      lexemeCache,
      node.id,
      fetchLexemeDetail,
    );
  }

  function handleNodeDblClick(node: TreeNode) {
    if (node.depth === 0) return;
    goto(treeUrl(node.langCode, node.headword));
  }

  function pickCandidate(etymKey: string) {
    goto(treeUrl(data.lang, data.headword, etymKey));
  }

  function dismissHomograph() {
    goto(resolve('/'));
  }

  function revertDetailOverride() {
    clickedDetail = null;
  }
</script>

<TreeShell
  bind:lang
  bind:headword
  status={data.status}
  queryLang={data.lang}
  queryHeadword={data.headword}
  slice={data.status === 'tree' ? data.slice : null}
  focusDetail={detail}
  candidates={data.status === 'homograph' ? data.candidates : []}
  {loading}
  onsearch={search}
  onrandom={randomWord}
  onnodeclick={handleNodeClick}
  onnodedblclick={handleNodeDblClick}
  onpickcandidate={pickCandidate}
  onhomographescape={dismissHomograph}
  ondetailescape={revertDetailOverride}
/>
