<!-- web/src/lib/LanguageCombobox.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import type { Language } from '../types';
  import { rankLanguages } from '../utils/languageSearch';

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
  let highlighted = $state(0);

  let suggestions = $derived(
    rankLanguages(value, languages).slice(0, MAX_SUGGESTIONS),
  );

  onMount(() => {
    fetch('/api/languages')
      .then((res) => (res.ok ? res.json() : []))
      .then((data: Language[]) => {
        languages = data;
      });
  });

  function select(lang: Language) {
    value = lang.code;
    open = false;
  }

  function onKeydown(e: KeyboardEvent) {
    if (!open || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      highlighted = (highlighted + 1) % suggestions.length;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      highlighted = (highlighted - 1 + suggestions.length) % suggestions.length;
    } else if (e.key === 'Enter' && highlighted < suggestions.length) {
      e.preventDefault();
      select(suggestions[highlighted]);
    } else if (e.key === 'Escape') {
      open = false;
    }
  }

  function onBlur() {
    // Defer so a click on an option fires before the listbox unmounts.
    setTimeout(() => {
      open = false;
    }, 150);
  }
</script>

<div class="combobox">
  <input
    class="lang-input"
    aria-label="Language code"
    role="combobox"
    aria-expanded={open && suggestions.length > 0}
    aria-controls="language-listbox"
    aria-autocomplete="list"
    autocomplete="off"
    bind:value
    {placeholder}
    oninput={() => {
      open = true;
      highlighted = 0;
    }}
    onfocus={() => (open = true)}
    onkeydown={onKeydown}
    onblur={onBlur}
  />
  {#if open && suggestions.length > 0}
    <ul class="listbox" id="language-listbox" role="listbox">
      {#each suggestions as lang, i (lang.code)}
        <li
          role="option"
          aria-selected={i === highlighted}
          class:highlighted={i === highlighted}
          onmousedown={(e) => {
            e.preventDefault();
            select(lang);
          }}
        >
          <span class="opt-code">{lang.code}</span>
          <span class="opt-name">{lang.name}</span>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .combobox {
    position: relative;
  }
  .lang-input {
    /* fits the longest real code, 'cmn-wadegiles' (13 chars) */
    width: 14ch;
    max-width: 100%;
    flex-shrink: 0;
    font-family: monospace;
    font-size: 1rem;
  }
  .listbox {
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
  .listbox li {
    display: flex;
    gap: 0.5rem;
    padding: 0.3rem 0.6rem;
    cursor: pointer;
    font-size: 0.9rem;
  }
  .listbox li.highlighted {
    background: var(--bg-2);
  }
  .opt-code {
    font-family: monospace;
    color: var(--tx-2);
    flex-shrink: 0;
  }
</style>
