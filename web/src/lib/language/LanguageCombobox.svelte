<!-- web/src/lib/LanguageCombobox.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { Combobox } from 'bits-ui';
  import type { Language } from '../shared/types';
  import { rankLanguages } from './languageSearch';
  import { apiFetch } from '../shared/apiFetch';

  // ponytail: fixed slice of the ranked list. ~2k rows rank in
  // microseconds, so this only bounds how many options render, not
  // how much work happens per keystroke.
  const MAX_SUGGESTIONS = 8;

  let {
    value = $bindable(),
    placeholder = '',
  }: {
    value: string;
    placeholder?: string;
  } = $props();

  let languages = $state<Language[]>([]);
  let open = $state(false);

  let suggestions = $derived(
    rankLanguages(value, languages).slice(0, MAX_SUGGESTIONS),
  );

  $effect(() => {
    if (open && suggestions.length === 0) open = false;
  });

  onMount(() => {
    apiFetch('/api/languages')
      .then((res) => (res.ok ? res.json() : []))
      .then((data: Language[]) => {
        languages = data;
      });
  });
</script>

<div class="combobox">
  <Combobox.Root
    type="single"
    bind:open
    inputValue={value}
    onValueChange={(code) => (value = code)}
  >
    <Combobox.Input
      class="lang-input"
      aria-label="Language code"
      autocomplete="off"
      {placeholder}
      oninput={(e) => {
        value = e.currentTarget.value;
        open = true;
      }}
    />
    <Combobox.ContentStatic class="listbox">
      {#each suggestions as lang (lang.code)}
        <Combobox.Item value={lang.code} label={lang.code}>
          <span class="opt-code">{lang.code}</span>
          <span class="opt-name">{lang.name}</span>
        </Combobox.Item>
      {/each}
    </Combobox.ContentStatic>
  </Combobox.Root>
</div>

<style>
  .combobox {
    position: relative;
  }
  :global(.lang-input) {
    /* fits the longest real code, 'cmn-wadegiles' (13 chars) */
    width: 14ch;
    max-width: 100%;
    flex-shrink: 0;
    font-family: monospace;
    font-size: 1rem;
  }
  :global(.listbox) {
    position: absolute;
    z-index: 10;
    top: 100%;
    left: 0;
    margin: 0.25rem 0 0;
    padding: 0.25rem 0;
    list-style: none;
    width: max-content;
    max-width: 20rem;
    max-height: 16rem;
    overflow-y: auto;
    background: var(--bg);
    border: 1px solid var(--ui-border);
    border-radius: 4px;
  }
  :global(.listbox [data-combobox-item]) {
    display: flex;
    gap: 0.5rem;
    padding: 0.3rem 0.6rem;
    cursor: pointer;
    font-size: 0.9rem;
  }
  :global(.listbox [data-combobox-item][data-highlighted]) {
    background: var(--bg-2);
  }
  .opt-code {
    font-family: monospace;
    color: var(--tx-2);
    flex-shrink: 0;
  }
</style>
