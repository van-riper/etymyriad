---
name: verify
description: Drive the etymyriad web app (SvelteKit) in a real headless browser to verify frontend changes, using the existing Playwright harness
---

# Verifying web/ changes

`svelte-check`/vitest catch type and pure-logic errors but miss real
rendering/interaction bugs. Always drive the app in a real browser for
any change touching `web/src/routes` or `web/src/lib`.

Playwright is already a `web/` devDependency (`web/e2e/`,
`playwright.config.ts`) — reuse it. Never bootstrap a separate
throwaway Playwright/Chromium install in `/tmp`.

## Setup

1. Local Postgres must be up with real data loaded (`make db-up`, or
   the native-Postgres fallback in the root `CLAUDE.md`).
2. From `web/`, run the existing suite first as a regression check:
   `npm run test:e2e`. Its `webServer` config starts `npm run dev` for
   you (see `playwright.config.ts`), so no manual server juggling is
   needed for a plain suite run.
3. To drive a specific interaction that isn't a spec yet, add a
   `*.spec.ts` file under `web/e2e/` (see `web/e2e/README.md`) and run
   just that file: `npx playwright test e2e/your-check.spec.ts`. If
   browsers aren't installed yet in this environment, run
   `npx playwright install chromium` once — Playwright itself is
   already in `node_modules`, no separate npm project needed.
4. Worth keeping? Leave the spec in `web/e2e/`. One-off only? Delete
   the file once done — but a "one-off" check is often worth keeping
   as real coverage instead, so check `web/e2e/` for gaps before
   deleting it.

## Driving it

- `/tree/[lang]/[headword]` is the primary view (SVG + d3-hierarchy):
  a focus word centered, ancestors/descendants laid out by BFS depth.
  `/graph` is still routable but renders nothing since the pivot to
  `/tree` — don't test it.
- Use Playwright's `getByRole`/`getByLabel` locators, per
  `web/e2e/README.md`'s convention, over CSS selectors.
- `web/e2e/smoke.spec.ts` is the canonical working example: the
  landing page and a real word's tree, both driven against live
  Postgres data.
- Real interactions worth driving end to end: clicking a non-focus
  tree node navigates to that word's own `/tree/[lang]/[headword]`;
  the random-word control fetches `/api/lexemes/random` and navigates
  to the result; a homograph headword renders a candidate list instead
  of a tree, and picking one navigates to the disambiguated URL (see
  `web/src/routes/tree/[lang]/[headword]/+page.svelte`).
