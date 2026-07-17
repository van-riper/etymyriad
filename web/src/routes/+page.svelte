<script lang="ts">
  import { goto } from '$app/navigation';
  import Badges from '$lib/Badges.svelte';

  let lang = $state('en');
  let headword = $state('etymology');

  function search() {
    goto(`/graph/${encodeURIComponent(lang)}/${encodeURIComponent(headword)}`);
  }
</script>

<svelte:head>
  <title>Etymyriad</title>
  <meta
    name="description"
    content="An interactive graph of words and their origins."
  />
  <link
    href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@700&display=swap"
    rel="stylesheet"
  />
</svelte:head>

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
        <input
          class="lang-input"
          aria-label="Language code"
          bind:value={lang}
          placeholder="en"
        />
      </div>
      <button type="submit">Search</button>
    </form>
  </div>

  <Badges />
</main>

<style>
  :global(html, body) {
    margin: 0;
    height: 100%;
    overflow: hidden;
  }
  main {
    display: flex;
    flex-direction: column;
    height: 100vh;
    font-family: system-ui, sans-serif;
  }
  input,
  button {
    font-family: inherit;
    font-size: 1rem;
  }
  .lang-input {
    width: 6ch;
    flex-shrink: 0;
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
    color: #666;
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
    color: #666;
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
