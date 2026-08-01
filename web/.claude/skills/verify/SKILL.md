---
name: verify
description: Drive the etymyriad web app (SvelteKit + cosmos.gl canvas) in a real headless browser to verify frontend changes
---

# Verifying web/ changes

`svelte-check`/vitest catch type and pure-logic errors but miss real
rendering/interaction bugs (cosmos.gl needs a live canvas). Always drive the
app in a real browser for any change touching `web/src/routes` or
`web/src/lib/graph.ts`.

## Setup

1. Local Postgres must be up with real data loaded (`make db-up`/`db-init`,
   or the native-Postgres fallback in the root `CLAUDE.md`). Confirm with:
   `curl -s localhost:PORT/api/position/en/etymology -o /dev/null -w '%{http_code}'`
   (expect `200`; the graph view itself lives at `/graph/en/etymology`,
   not an API route).
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
   `chromium.launch()`, `page.goto('http://localhost:<port>/graph/en/etymology')`.
4. Clean up afterward: kill the dev server (find its real PID with
   `ss -ltnp | grep <port>`, not `pkill -f "vite dev"` — that pattern can
   match your own shell command line and kill the wrong process), then
   `rm -rf /tmp/etym-verify`.

## Driving it

- Wait for `canvas` to appear, then `waitForTimeout(~1500ms)` for
  cosmos.gl's first render to settle before screenshotting or clicking.
  Node positions come from a real precomputed layout (`lexeme_layout`,
  see the root `CLAUDE.md`), not client-side math, so the same word
  renders at the same relative positions across runs — unlike the old
  client-jittered ring layout this replaced (ETYM-71).
- cosmos.gl renders as a **single `<canvas>` element**. Asserting
  `canvas elements: 1` is correct — don't expect Sigma's old multi-layer
  stack.
- Nodes carry **no default label**; only the focus node is visually
  distinct (larger, a different color). Hovering a node (debounced
  ~150ms) shows a tooltip with its real headword/gloss — there's no way
  to identify a specific non-focus node from the canvas alone before
  hovering it.
- To click a specific non-focus node without knowing its exact screen
  coordinates in advance: screenshot first to locate the focus node (the
  visually distinct dot near the render's center), then try a small
  spiral/grid of offsets around it (several radii × several angles) until
  a click actually changes `page.url()` — don't hardcode a single offset
  guess, since a real layout places neighbors at unpredictable angles
  around any given focus word.
- Clicking empty canvas space is a legitimate no-op probe (cosmos.gl's
  `onPointClick` callback only fires for an actual point hit).
- To test click-to-navigate end to end: click a neighbor node (see
  above), then read the two search `input` values via
  `page.$$eval('input', els => els.map(e => e.value))` — they should
  update to the clicked node's `lang`/`headword`, and the canvas should
  re-render around a new focus node. Clicking a *second* neighbor
  immediately after confirms the click handler correctly re-attaches on
  every re-render (each navigation calls `renderer?.destroy()` then
  constructs a fresh cosmos.gl `Graph` instance).
