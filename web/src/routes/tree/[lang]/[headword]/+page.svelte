<script lang="ts">
  import { goto } from '$app/navigation';
  import { page, navigating } from '$app/state';
  import SidePanel from '$lib/components/SidePanel.svelte';
  import TreeDiagram from '$lib/components/TreeDiagram.svelte';
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

<main>
  <SidePanel
    bind:lang
    bind:headword
    nodeCount={data.status === 'tree' ? data.slice.nodes.length : 0}
    focusDetail={data.status === 'tree' ? data.focusDetail : null}
    {loading}
    onsearch={search}
    onrandom={randomWord}
  />

  <div class="content">
    {#if data.status === 'notfound'}
      <p class="error" role="alert">
        No matches for "{data.headword}" ({data.lang}).
      </p>
    {/if}

    {#if data.status === 'homograph'}
      <div class="homograph-picker">
        <p>
          "{data.headword}" ({data.lang}) has {data.candidates.length}
          distinct entries. Pick one:
        </p>
        <ul>
          {#each data.candidates as candidate (candidate.id)}
            <li>
              <button
                type="button"
                onclick={() => pickCandidate(candidate.etymKey)}
              >
                {#if candidate.pos}<span class="candidate-pos"
                    >{candidate.pos}</span
                  >{/if}
                {candidate.gloss ?? '(no gloss)'}
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if data.status === 'tree'}
      <TreeDiagram slice={data.slice} onnodeclick={handleNodeClick} />
    {/if}
  </div>
</main>

<style>
  main {
    display: flex;
    flex-direction: row;
    height: 100vh;
    background: var(--bg);
    color: var(--tx);
    font-family: system-ui, sans-serif;
  }
  .content {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
  }
  .error {
    margin: 1rem;
    padding: 0.5rem 0.75rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 6px;
    font-size: 0.9rem;
    color: var(--danger);
    border-color: var(--danger);
  }
  .homograph-picker {
    padding: 1rem;
    overflow-y: auto;
  }
  .homograph-picker ul {
    list-style: none;
    margin: 0.5rem 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .homograph-picker button {
    width: 100%;
    text-align: left;
    padding: 0.5rem 0.75rem;
    background: var(--bg-2);
    border: 1px solid var(--ui-border);
    border-radius: 6px;
    color: var(--tx);
    font-size: 0.95rem;
    cursor: pointer;
  }
  .homograph-picker button:hover {
    border-color: var(--tx-2);
  }
  .candidate-pos {
    color: var(--tx-2);
    font-style: italic;
    margin-right: 0.4rem;
  }
</style>
