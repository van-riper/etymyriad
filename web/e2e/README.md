# e2e tests

Playwright specs that drive a real browser against a real dev server
and a real Postgres database (`db.ts`'s local-dev `DATABASE_URL`
default, or `web/.env` to override it), unlike the mocked-DB unit
tests under `src/`.

Run them with:

```sh
npm run test:e2e
```

This starts `npm run dev` automatically (see `playwright.config.ts`'s
`webServer`) if one isn't already running on port 5173, so a database
must be reachable via `DATABASE_URL` first (`make db-up`).

## Adding a spec

Add a `*.spec.ts` file to this directory. Each spec gets a fresh
`page` fixture; use `page.goto('/some/path')` (relative to `baseURL`)
and Playwright's `expect(locator).toBeVisible()`-style assertions.
Prefer `getByRole`/`getByLabel` over CSS selectors, since they fail
loudly when accessibility semantics regress.

The landing page (`/`) has no async load function, so it can render
before Svelte finishes hydrating -- a plain `.click()`/`.fill()` right
after `page.goto('/')` can land on a not-yet-listening element and
silently no-op. Routes with a data load (e.g. `/tree/[lang]/[headword]`)
don't have this problem: by the time they render, the load's fetches
have already given hydration time to finish. For the first interaction
on `/`, retry it until its effect actually shows up, instead of a fixed
sleep:

```ts
await expect(async () => {
  await button.click();
  await expect(theEffect).toBeVisible({ timeout: 500 });
}).toPass();
```
