# e2e tests

Playwright specs that drive a real browser against a real dev server
and a real Postgres database (`web/.env`'s `DATABASE_URL`), unlike the
mocked-DB unit tests under `src/`.

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
