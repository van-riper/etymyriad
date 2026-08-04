<script lang="ts">
  import { goto } from '$app/navigation';
  import LanguageCombobox from '$lib/components/LanguageCombobox.svelte';
  import { headwordError, langCodeError } from '$lib/utils/validation';
  import { treeUrl } from '$lib/utils/treeUrl';

  let lang = $state('en');
  let headword = $state('etymology');
  let error = $state<string | null>(null);

  function search() {
    error = headwordError(headword) ?? langCodeError(lang);
    if (error) return;
    goto(treeUrl(lang, headword));
  }
</script>

<main>
  <div class="landing">
    <h1>Etymyriad</h1>
    <p class="author">By: Finn van Riper</p>
    <p class="lead">An interactive graph of words and their origins.</p>
    <p class="lead">
      Trace the etymology of any <i>lexeme</i> (word) in any language back
      through each <i>etymon</i> (word ancestor) that influenced it, and explore
      its cognates, derivatives, and roots!
    </p>
    <form
      class="landing-search"
      onsubmit={(e) => {
        e.preventDefault();
        search();
      }}
    >
      <p class="landing-search-hint">
        Enter a word and language code, then hit Search.
      </p>
      <div class="landing-search-inputs">
        <input
          class="headword-input"
          aria-label="Headword"
          bind:value={headword}
          placeholder="etymology"
        />
        <LanguageCombobox bind:value={lang} placeholder="en" />
      </div>
      <button type="submit">Search</button>
      <p class="landing-search-error" class:visible={!!error}>
        {error ?? ' '}
      </p>
    </form>
  </div>
</main>

<style>
  main {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--bg);
    color: var(--tx);
    font-family: system-ui, sans-serif;
  }
  input,
  button {
    font-family: inherit;
    font-size: 1rem;
  }
  .headword-input {
    width: 12rem;
  }
  .landing {
    margin: auto;
    max-width: 32rem;
    padding: 0 1rem;
    text-align: center;
  }
  .landing h1 {
    margin: 0;
    font-family: 'Libre Baskerville', serif;
    font-weight: 700;
    font-size: 2.5rem;
  }
  .author {
    margin: 0.5rem 0 0;
    font-size: 0.9rem;
    color: var(--tx-2);
  }
  .landing .lead {
    margin-top: 1rem;
    line-height: 1.5;
  }
  .landing-search {
    margin-top: 1rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
  }
  .landing-search-hint {
    margin: 0;
    font-size: 0.95rem;
    color: var(--tx-2);
  }
  .landing-search-error {
    margin: 0;
    font-size: 0.9rem;
    color: var(--danger);
    visibility: hidden;
  }
  .landing-search-error.visible {
    visibility: visible;
  }
  .landing-search-inputs {
    margin-top: 0.5rem;
    display: flex;
    gap: 0.5rem;
  }
  .landing-search button {
    margin-top: 0.5rem;
    padding: 0.5rem 1.5rem;
  }
</style>
