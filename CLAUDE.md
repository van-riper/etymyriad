# CLAUDE.md

Guidance for Claude Code working in the **etymyriad** repository.

## What this is

etymyriad is an **etymology network visualizer**: explore the ancestry,
descendants, and cognates of words as an interactive graph, backed by a
**sourced, citable** dataset. The name is _etymology + myriad_ ("a myriad of
word origins").

Audience: a portfolio/learning showcase that doubles as a public tool for
language enthusiasts, held to research-grade accuracy.

Full rationale for every foundational decision is in
[`docs/DESIGN.md`](docs/DESIGN.md). Read it before proposing architectural
changes.

## Current status

The ETL is implemented and verified at scale: `normalize._edges_from_entry`
is done, the full Indo-European Wiktextract dataset is acquired
(`data/raw/indo-european.jsonl`, gitignored, 8.3M entries across 443
languages via the `filter-ine` CLI step), and a full `parse -> normalize ->
load` run has loaded a real graph locally (3.19M edges, 2.47M lexemes,
1.4GB), verified with a real recursive-CTE backtrace: `water` (en) ->
`watōr` (gem-pro) -> `wódr̥` (ine-pro). Loading the same dataset into Neon
is in progress. The web app has a first working landing page: a search box
wired to `/api/word/[lang]/[headword]` rendering the result via
Sigma.js/graphology (`web/src/routes/+page.svelte`, `web/src/lib/graph.ts`).
It is unstyled and shows the whole ego-network with no filtering, so dense
words (e.g. `water` at depth 2, 673 nodes) are unreadable -- the anti-noise
UX (Open item 4) is not built yet. `web/src/lib/server/db.ts` uses the
`postgres` package for local dev (real TCP, since Neon's driver only speaks
to Neon's own HTTP endpoint) and keeps `neon()` for the Cloudflare
production path.

## Architecture

```mermaid
flowchart LR
    dump["Wiktextract dump"] -->|offline, periodic| etl["Python ETL<br/>(etl/)"]
    etl -->|writes rows| db[("Postgres<br/>(Neon)")]
    db -->|recursive-CTE queries| web["SvelteKit<br/>(web/, Cloudflare Pages)"]
    web -->|ego-network JSON| canvas["Sigma.js canvas<br/>(browser)"]
```

Two languages, each where it is strongest, with Postgres as the clean boundary.
The ETL is isolated: it runs offline and only writes rows, so it shares no
code with the app. The web app is **both** the frontend and the API (SvelteKit
`+server.ts` routes query Postgres directly, with no separate API service).

## Repo layout

| Path                                         | Purpose                                                            |
| -------------------------------------------- | ------------------------------------------------------------------ |
| `db/schema.sql`                              | Canonical Postgres schema. The source of truth for the data model. |
| `db/migrations/`                             | Ordered SQL migrations (baseline mirrors `schema.sql`).            |
| `etl/`                                       | Python ETL (uv, src layout). Parses Wiktextract into the graph.    |
| `etl/src/etymyriad/`                         | `parse` -> `normalize` -> `load`. `model` mirrors the SQL.         |
| `web/`                                       | SvelteKit app (frontend + API).                                    |
| `web/src/lib/types.ts`                       | Graph types shared by API and UI. Mirror of the schema.            |
| `web/src/lib/server/`                        | Server-only DB client and queries.                                 |
| `web/src/routes/api/word/[lang]/[headword]/` | Ego-network endpoint.                                              |
| `docs/DESIGN.md`                             | Foundation design doc (decisions + rationale).                     |

## Data model invariants (do not violate)

The model is a directed, provenance-carrying graph (`db/schema.sql`):

- **`lexeme`** = a node (a word/morpheme in one language).
- **`etymology`** = a directed edge, `src -> dst` meaning **ancestor ->
  descendant**.
- **Every edge carries a `source_ref`** back to its Wiktionary origin. Nothing
  in the graph is unsourced. This is what makes the dataset citable.
- **Never generate etymological facts with AI.** The graph is deterministic and
  sourced. AI (deferred) may later summarize or search over it, never author it.
- **Never render the whole graph.** Every view is a depth-limited **ego-network**
  (the anti-noise primitive). The browser only ever sees a focused slice.
- Edge direction matters: backtrace walks `dst -> src`, and descendants walk
  `src -> dst`. Traversals use Postgres recursive CTEs.

If you change `db/schema.sql`, update both `etl/.../model.py` and
`web/src/lib/types.ts` to match.

## Tech stack and locked decisions

Do not relitigate these without a reason. They were chosen deliberately.

| Area         | Choice                       | Why                                                        |
| ------------ | ---------------------------- | ---------------------------------------------------------- |
| v1 scope     | Indo-European family         | Best Wiktionary coverage, richest chains.                  |
| Data source  | Wiktextract / kaikki.org     | Machine-readable, cited. Validate vs Etymological Wordnet. |
| ETL          | Python 3.13 (uv)             | Wiktextract is Python. Best data/NLP ecosystem.            |
| DB           | Postgres on **Neon**         | Recursive CTEs for traversal, serverless free tier.        |
| App + API    | **SvelteKit** (TypeScript)   | One codebase, shared types. Server routes are the API.     |
| Graph render | **Sigma.js v3 + graphology** | WebGL, scales to 10k+ nodes.                               |
| Hosting      | **Cloudflare Pages** + Neon  | `adapter-cloudflare`. Routes run as Pages Functions.       |
| Domain       | etymyriad.com                | Matches repo = package = domain.                           |
| AI           | Deferred                     | Designed-for, not built.                                   |

## Conventions

Python is uv-managed with **ruff** (`ruff format`, `ruff check`) at 80 cols,
src layout. Keep ETL dependencies minimal and justify each
addition in the PR. Before committing ETL changes, run
`uv run ruff format && uv run ruff check && uv run ty check && uv run pytest`
(or `make lint ty test`). TypeScript/Svelte
uses 2-space indentation and must keep `svelte-check` clean, with server-only
code confined to `lib/server/`. The Google Python and TypeScript style guides
are the definitive baselines.

**Commits:** Conventional Commits. End commit messages with the
`Co-Authored-By` trailer. Branch off the default branch for feature work.

**General** (from the user's global CLAUDE.md): concise explanations, prefer
composition over inheritance, show the verify command for changes.

**Development discipline (TDD):** All feature work and bugfixes in this repo go
through test-driven development. Write the failing test first, watch it fail for
the right reason, then write the minimal code to pass, then refactor. The Iron
Law holds: no production code without a failing test first. Code written before
its test gets deleted and rewritten from the test, not adapted in place. This
covers the ETL (`uv run pytest`) and the web app (`npm run check` plus
vitest); a `svelte-check` error counts as a failing test. Narrow exceptions
(throwaway spikes, generated code, pure config) need a heads-up first, never a
silent skip. A golden-test divergence is a parser bug: fix the parser, never
edit the golden value to match buggy output.

## Common commands

```sh
# Database (local dev, via podman; see Local-dev gotchas if this fails)
make db-up         # start local Postgres
make db-init       # apply db/schema.sql
make db-psql       # psql shell
make db-reset      # wipe + re-init

# ETL (Python)
cd etl && uv sync
uv run pytest
uv run ruff check        # lint
uv run ruff format       # format
uv run ty check          # type-check
uv run etymyriad parse   # inspect the dump
uv run etymyriad all     # parse + normalize + load

# Web (frontend + API)
cd web && npm install
npm run dev        # local dev server
npm run check      # svelte-check (must be clean)
npm run build      # production build via Cloudflare adapter
```

## Local-dev gotchas

- **System Python is 3.14**, too new for some data-lib wheels. The ETL is
  pinned to **3.13** via `etl/.python-version`, and uv fetches it
  automatically.
  Do not "upgrade" this without checking wheel availability.
- **The Neon serverless driver talks HTTP only to Neon's own endpoint, never
  to a plain local Postgres** -- `Pool`/`Client` included, since those still
  go through Neon's WebSocket proxy. `web/src/lib/server/db.ts` resolves
  this with a dev/prod split: in dev (SvelteKit's `dev` flag) it dynamically
  imports the `postgres` package for a real TCP connection to local
  Postgres; in prod it keeps `neon()` for the Cloudflare Workers runtime,
  which can't open raw TCP sockets. `web/.env`'s `DATABASE_URL` should point
  at local Postgres (`postgres://etymyriad:etymyriad@localhost:5432/etymyriad`)
  for day-to-day dev.
- `DATABASE_URL` and `WIKTEXTRACT_DUMP` come from `.env` (see `.env.example`).
  `.env` is gitignored.
- The DB client is created **lazily** (`web/src/lib/server/db.ts`) so the
  build does not require `DATABASE_URL`. Keep it lazy.
- **Sigma.js needs WebGL, which does not exist during SvelteKit's SSR
  render.** A static top-level `import Sigma from 'sigma'` in a `.svelte`
  file crashes every page load with `WebGL2RenderingContext is not defined`.
  Import it lazily (e.g. inside the click/fetch handler, not at module
  scope) so it only loads in the browser.
- **`graphology`'s default `Graph` rejects parallel edges.** Two lexemes can
  be linked by more than one `rel_type` (e.g. both `derived` and `cognate`
  are separate DB rows), which throws `UsageGraphError` unless the graph is
  constructed with `multi: true` (`web/src/lib/graph.ts`).
- **`make db-up` (podman compose) can fail outright.** On at least one dev
  box, rootless podman had no compose provider at all, and a plain
  `podman run` then hit a fatal userns error (reproduced even on
  `podman ps -a`) -- a system-wide podman break, not project-specific.
  Fallback: install `postgresql-server` as a native package (a layered rpm
  on an atomic/immutable Fedora variant), then
  `sudo postgresql-setup --initdb && sudo systemctl enable --now postgresql`.
  Fedora's default `pg_hba.conf` uses `ident` for TCP (`host`) connections,
  which rejects a `postgres://user:pass@localhost/...` DSN; change the
  `127.0.0.1/32`/`::1/128` `host` lines' method to `scram-sha-256` and
  `sudo systemctl reload postgresql` before a role can log in over TCP.
  Then create the `etymyriad` role/database matching `.env.example` via
  `sudo -u postgres psql`, and apply `db/schema.sql` directly with `psql`
  (no container needed at all once this is done).

## Open items / yet-to-be-determined

Implementation, roughly in order:

1. ~~`normalize._edges_from_entry`~~ **Done.** Parses `etymology_templates`
   into `EtymEdge`s via `TEMPLATE_RELS`, including a same-word self-loop
   guard (`_maybe_edge`) found by running the full real dump. Etymological
   Wordnet validation was deliberately deferred rather than built (see
   Decisions still open).
2. **Seed the `language` table** with real names/families. `is_proto` is
   done (derived from the existing `-pro` code suffix, verified against the
   real dump with zero exceptions either direction). `name`/`family` are
   still bare-code rows: `load.py`'s `_ensure_languages` never sees a
   human-readable name by the time it runs, so this needs either threading
   `entry["lang"]` through from `normalize`, or a separately sourced
   code -> name/family table.
3. ~~Acquire data~~ **Done.** `data/raw/indo-european.jsonl` (gitignored,
   8.3M entries across 443 languages) replaces the old
   `proto-germanic.jsonl`/`proto-indo-european.jsonl` samples. kaikki.org
   deprecated its per-language exports in favor of one combined dump
   (`raw-wiktextract-data.jsonl.gz`, every language mixed together);
   `etymyriad filter-ine` (`etl/src/etymyriad/languages.py`) narrows it to
   Indo-European by matching Wiktionary's own `lang` names, crawled from
   `Category:Indo-European languages`.
4. **Frontend graph view:** the landing-page search is now wired to a
   Sigma.js canvas backed by `/api/word/:lang/:headword`
   (`web/src/routes/+page.svelte`, `web/src/lib/graph.ts`), verified
   end-to-end against real local data. Still needed: the anti-noise UX
   (click-to-expand, rel-type/language filters, level-of-detail) -- dense
   words currently render as an unreadable tangle (e.g. `water` at depth 2
   is 673 nodes). Styling is also still bare-bones.
5. **Backtrace endpoint + view:** linear ancestor chain for any word. Not
   started, but the underlying recursive CTE is proven against real local
   data: `water` (en) -> `watōr` (gem-pro) -> `wódr̥` (ine-pro).

Done: GitHub repo is public
(`github.com/van-riper/etymyriad`), **etymyriad.com** is registered and live
via a Cloudflare Pages project auto-deploying on push to `main`, CI is
green, and a full real-data ETL run is verified locally (3.19M edges, 2.47M
lexemes, 1.4GB).

Accounts / infra still to set up (by the user):

- Neon account + project, with `DATABASE_URL` wired as a local `.env` entry
  for the ETL and (once a route needs it) a Cloudflare Pages secret. In
  progress as of 2026-07-10.

Decisions still open:

- Whether to add a migration runner (dbmate/atlas) once the schema churns.
  Plain ordered SQL for now.
- **Homograph/sense splitting, fixed 2026-07-10.** The old lexeme natural
  key `(lang_code, headword, COALESCE(gloss, ''))` split nodes by
  POS/gloss, which was the wrong signal: Wiktextract already tags each
  entry with `etymology_number`, and real data shows it's the correct
  one. Checked `en:underwater` directly in the raw dump: adj/adv/noun
  senses all share `etymology_number: 1` (same derivation, "under" +
  "water") while its verb sense is genuinely separate at
  `etymology_number: 2` -- the old key rendered all four as separate
  same-labeled nodes in the graph, which was misleading. Nodes now key
  on `etymology_number` instead of `gloss`; `gloss`/`pos` moved off
  `lexeme` into a new `sense` table (one lexeme -> many senses), while
  the node/edge/source_ref graph model itself is unchanged. Still open:
  whether disambiguation needs `pos` too for the `bh` case (Wiktionary's
  `bh` code covers both Bihari and Bhojpuri, so a word from each sharing
  headword/gloss would still collide under the current key).
- Whether/when to enable AI features (NL search, prose summaries).

Future feature specs (each a read over the same schema, own design doc):
individual word breakdown pages (SEO/SSG), word -> country/region map, cognate
explorer.

## References

- `docs/DESIGN.md`: foundation design and rationale.
- Wiktextract / kaikki.org: https://kaikki.org
- Etymological Wordnet: validation source.
