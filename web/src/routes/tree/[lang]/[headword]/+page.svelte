<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { page, navigating } from '$app/state';
  import TreeShell from '$lib/tree/TreeShell.svelte';
  import { treeUrl } from '$lib/tree/url';
  import { cachedTermDetail } from '$lib/tree/termCache';
  import { apiFetch } from '$lib/shared/apiFetch';
  import { displayHeadword } from '$lib/tree/headword';
  import type { Term, TreeNode } from '$lib/shared/types';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  let lang = $state(page.params.lang as string);
  let headword = $state(page.params.headword as string);
  let fetchingRandom = $state(false);
  const loading = $derived(!!navigating.to || fetchingRandom);

  // Detail for the last single-clicked node, shown in the detail
  // panel in place of the focus word's own detail. Reset on
  // navigation so the new focus word's detail takes back over.
  let clickedDetail = $state<Term | null>(null);
  const termCache = new Map<number, Term>();
  const detail = $derived(
    clickedDetail ?? (data.status === 'tree' ? data.focusDetail : null),
  );
  const focusDetail = $derived(
    data.status === 'tree' ? data.focusDetail : null,
  );
  const tabTitle = $derived(
    focusDetail
      ? `${displayHeadword(focusDetail.headword, focusDetail.isReconstructed)} (${focusDetail.langName}) · Etymyriad`
      : 'Etymyriad',
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

  async function fetchTermDetail(id: number): Promise<Term | null> {
    const res = await apiFetch(`/api/terms/${id}`);
    if (!res.ok) return null;
    return await res.json();
  }

  let latestClickedNodeId: number | null = null;

  async function handleNodeClick(node: TreeNode) {
    latestClickedNodeId = node.id;
    const result = await cachedTermDetail(termCache, node.id, fetchTermDetail);
    if (latestClickedNodeId !== node.id) return;
    clickedDetail = result;
  }

  function handleNodeDblClick(node: TreeNode) {
    if (node.depth === 0) return;
    goto(treeUrl(node.langCode, node.headword));
  }

  function pickCandidate(section: number) {
    goto(treeUrl(data.lang, data.headword, section));
  }

  function dismissHomograph() {
    goto(resolve('/'));
  }

  function revertDetailOverride() {
    clickedDetail = null;
  }
</script>

<svelte:head>
  <title>{tabTitle}</title>
</svelte:head>

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
