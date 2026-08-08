<script lang="ts">
  import { page } from '$app/state';
</script>

<main>
  <h1>{page.status}</h1>
  <p>{page.error?.message ?? 'Something went wrong.'}</p>
</main>

<style>
  main {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 0.5rem;
    text-align: center;
  }
  h1 {
    margin: 0;
    font-size: 3rem;
    color: var(--tx);
  }
  p {
    margin: 0;
    color: var(--tx-2);
  }
</style>
