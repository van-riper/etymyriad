---
name: verify
description: Drive the etymyriad web app (SvelteKit + Sigma.js canvas) in a real headless browser to verify frontend changes
---

# Verifying web/ changes

`svelte-check`/vitest catch type and pure-logic errors but miss real
rendering/interaction bugs (Sigma.js needs a live canvas). Always drive the
app in a real browser for any change touching `web/src/routes` or
`web/src/lib/graph.ts`.

## Setup

1. Local Postgres must be up with real data loaded (`make db-up`/`db-init`,
   or the native-Postgres fallback in the root `CLAUDE.md`). Confirm with:
   `curl -s localhost:PORT/api/word/en/water?depth=2 -o /dev/null -w '%{http_code}'`
2. Start the dev server in the background: `npm run dev` (from `web/`). It
   tries port 5173 first but falls back to 5174+ if something else is
   already listening — read the actual port from its stdout, don't assume
   5173.
3. No `playwright`/`chromium-cli` is preinstalled in this environment. Get a
   real headless Chrome once per environment, in `/tmp` (not the repo, no
   project dependency):
   ```sh
   mkdir -p /tmp/etym-verify && cd /tmp/etym-verify
   npx --yes playwright install chromium   # note the chromium-<rev> it downloads
   npm init -y && npm install playwright-core@<matching version> --no-save
   ```
   Drive it with a small `.mjs` script importing
   `chromium` from `/tmp/etym-verify/node_modules/playwright-core/index.mjs`,
   `chromium.launch()`, `page.goto('http://localhost:<port>/')`.
4. Clean up afterward: kill the dev server (find its real PID with
   `ss -ltnp | grep <port>`, not `pkill -f "vite dev"` — that pattern can
   match your own shell command line and kill the wrong process), then
   `rm -rf /tmp/etym-verify`.

## Driving it

- Wait for `canvas` to appear, then `waitForTimeout(~1500ms)` for Sigma's
  first render/layout to settle before screenshotting or clicking.
- The graph layout is a plain circle (`buildGraph` in `graph.ts`, no force
  layout installed), so node screen positions are **not stable across
  runs** — response order from Postgres isn't guaranteed, so angle
  assignment shifts. Screenshot first, read node label positions off the
  image, then click near the dot (labels sit to the side of the dot facing
  away from the circle center) rather than hardcoding coordinates from a
  previous run.
- Clicking empty canvas space is a legitimate no-op probe (no `clickNode`
  event fires).
- To test click-to-navigate end to end: click a neighbor node, then read
  the two search `input` values via
  `page.$$eval('input', els => els.map(e => e.value))` — they should
  update to the clicked node's `lang`/`headword`, and the canvas should
  re-render around a new focus node. Clicking a *second* neighbor
  immediately after confirms the click handler correctly re-attaches on
  every re-render (each `search()` call creates a fresh `Sigma` instance).
