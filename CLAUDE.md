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
load` run has loaded a real graph locally (2.99M edges, 2.08M lexemes,
after the schema moved to UUID keys and split `gloss`/`pos` into a `sense`
table), verified with a real recursive-CTE backtrace: `etymology` (en) ->
`etymologia` (la) -> `ἐτυμολογία` (grc). The backend database is **Neon**
(`DATABASE_URL` points at a `neon.tech` instance); the full dataset is
loaded there (2,075,078 lexemes, 2,993,290 edges, 1,604,538 senses, 1,944
languages), verified with the same recursive-CTE backtrace as the local
load. `lexeme_layout` holds a precomputed DrL force-directed `(x, y)` per
lexeme (igraph, via the `etymyriad layout` CLI step), indexed with a GiST
`pos` point column for both bounding-box and nearest-neighbor queries.

On 2026-08-04 the project pivoted away from full-graph visualization as
the primary UI. `/graph`'s cosmos.gl force-directed view (viewport
tiling, the binary wire format, the precomputed DrL layout) was retired
outright (ETYM-110), the same precedent as the earlier ring-jitter
ego-network retirement: `/graph/[lang]/[headword]` is still routable but
renders nothing. The new primary UI is `/tree/[lang]/[headword]`
(ETYM-109, not yet built): a bounded genealogy chart, focus word
centered, ancestor/descendant generations layered by BFS depth, laid
out deterministically (no physics). What `/graph` leaves behind and
`/tree` reuses: `web/src/lib/server/db.ts`, `/api/lexemes/[id]`
(per-node detail on hover/click), `/api/lexemes/random`, `/api/languages`,
`LanguageCombobox`, `lexemeCache.ts`, `SidePanel.svelte`, and the shared
page shell (title/meta/`Badges`) in `web/src/routes/+layout.svelte`.
`lexeme_layout` (the precomputed DrL `(x, y)` per lexeme, GiST-indexed)
is left in place unused by the web app -- not a `/tree` concern, since
`/tree` lays out nodes from BFS depth and sibling order, not spatial
coordinates. `web/src/lib/server/db.ts` uses the `postgres` package for
local dev (real TCP, since Neon's driver only speaks to Neon's own HTTP
endpoint) and `neon()` for the Cloudflare production path.

## Architecture

```mermaid
flowchart LR
    dump["Wiktextract dump"] -->|offline, periodic| etl["Python ETL<br/>(etl/)"]
    etl -->|writes rows| db[("Postgres<br/>(Neon)")]
    db -->|recursive-CTE queries| web["SvelteKit<br/>(web/, Cloudflare Pages)"]
    web -->|bounded BFS slice| canvas["cosmos.gl canvas<br/>(browser)"]
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
| `web/src/lib/shared/`                        | Cross-cutting: `types.ts`, `apiFetch.ts`, `validation.ts`, `Badges.svelte`. |
| `web/src/lib/theme/`                         | Theme store (`store.svelte.ts`), styles (`variables.css`), `ThemeToggle.svelte`. |
| `web/src/lib/tree/`                          | `/tree` feature: `TreeDiagram`/`TreeShell`, plus its private `layout/`, URL, and cache helpers. |
| `web/src/lib/language/`                      | `LanguageCombobox` and its private `languageSearch.ts` ranking helper. |
| `web/src/lib/server/`                        | Server-only DB client and queries.                                 |
| `web/src/routes/api/lexemes/[id]/`           | Lazy per-node detail (senses, `source_ref`).                       |
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
- **Never render the whole graph.** Every view is a bounded slice around one
  focus word (`/tree`'s bounded BFS, once built), never a fetch of the whole
  table. The browser only ever sees a focused slice.
- Edge direction matters: backtrace walks `dst -> src`, and descendants walk
  `src -> dst`. Traversals use Postgres recursive CTEs.

If you change `db/schema.sql`, update both `etl/.../model.py` and
`web/src/lib/shared/types.ts` to match.

## Tech stack and locked decisions

Do not relitigate these without a reason. They were chosen deliberately.

| Area         | Choice                                   | Why                                                        |
| ------------ | ---------------------------------------- | ---------------------------------------------------------- |
| v1 scope     | Indo-European family                     | Best Wiktionary coverage, richest chains.                  |
| Data source  | Wiktextract / kaikki.org                 | Machine-readable, cited. Validate vs Etymological Wordnet. |
| ETL          | Python 3.13 (uv)                         | Wiktextract is Python. Best data/NLP ecosystem.            |
| DB           | **Neon** (serverless Postgres)           | Recursive CTEs for traversal                               |
| App + API    | **SvelteKit** (TypeScript)               | One codebase, shared types. Server routes are the API.     |
| Graph render | **cosmos.gl**                            | WebGL, static mode (no live simulation), scales to the full ~2M-node/~3M-edge graph (ETYM-77: ~1.6s load, 894MB JS heap, steady 60fps pan/zoom). |
| Hosting      | **Cloudflare Pages** + Neon              | `adapter-cloudflare`. Routes run as Pages Functions.       |
| Domain       | etymyriad.com                            | Matches repo = package = domain.                           |
| AI           | Deferred                                 | Designed-for, not built.                                   |

## Conventions

Python is uv-managed with **ruff** (`ruff format`, `ruff check`) at 80 cols,
src layout. Keep ETL dependencies minimal and justify each addition in the PR.
Before committing ETL changes, run `make etl-lint etl-ty etl-cov`. TypeScript/Svelte uses
2-space indentation and must keep `svelte-check` clean, with server-only code
confined to `lib/server/`. The Pythonicator canon is the primary source for
Python style, while the Google Python style guide is a fallback. The Google
TypeScript style guide is the definitive baseline for Typescript.

**Commits:** Conventional Commits. End commit messages with the coauthor
trailer, except version-bump commits (`chore: bump to vX.Y.Z`): those are
run by the user via `make release-bump-commit`, not authored by Claude, and carry
no trailer. Branch off `dev` for feature work and merge back into `dev`
when done. `main` tracks releases: `dev` merges into `main` on a version
bump, not before.

**Changelog:** `CHANGELOG.md` is generated from Conventional Commits by
[git-cliff](https://git-cliff.org)'s bundled `keepachangelog` config, no
local `cliff.toml`, since the built-in preset already matches this
repo's history exactly. `make release-bump VERSION=vX.Y.Z` regenerates it,
bumps the `etl`/`web` versions and their lockfiles, and stages the lot;
`make release-bump-commit VERSION=vX.Y.Z` does the same and also commits it as
`chore: bump to vX.Y.Z` and tags it (see Common commands). No CI
publishing step, since there's no audience for GitHub releases yet.

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
edit the golden value to match buggy output. Browser-driven verification for
`web/` changes goes through the checked-in Playwright harness
(`web/e2e/`, `npm run test:e2e`; see the `verify` skill), never a throwaway
script in `/tmp`. An interaction worth checking once is usually worth
keeping: add it as a spec in `web/e2e/` rather than discarding it after a
one-off manual check.

## Common commands

```sh
# Database (local dev, native Postgres via systemctl)
make db-up         # start local Postgres
make db-down       # stop local Postgres
make db-apply       # apply db/schema.sql to $DATABASE_URL (local by default)
make db-psql       # psql shell
make db-reset      # wipe + re-init local database
make db-apply DATABASE_URL=...  # apply schema to a remote DB (e.g. Neon)

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
npm run test:e2e   # Playwright e2e specs (web/e2e/), against a real dev server + DB
npm run build      # production build via Cloudflare adapter

# Release (bump + tag)
make release-bump VERSION=vX.Y.Z         # changelog + etl/web versions + lockfiles, staged only
make release-bump-commit VERSION=vX.Y.Z  # same, plus commit + tag, on dev
git push origin main vX.Y.Z              # after ff-merging dev into main
```

## Local-dev gotchas

- **System Python is 3.14**, too new for some data-lib wheels. The ETL is
  pinned to **3.13** via `etl/.python-version`, and uv fetches it
  automatically.
  Do not "upgrade" this without checking wheel availability.
- **The Neon serverless driver talks HTTP only to Neon's own endpoint, never
  to a plain local Postgres** -- `Pool`/`Client` included, since those still
  go through Neon's WebSocket proxy. `web/src/lib/server/db.ts` resolves
  this with a dev/prod split: dev dynamically imports the `postgres` package
  for a real TCP connection to local Postgres; prod keeps `neon()` for the
  Cloudflare Workers runtime, which can't open raw TCP sockets. In prod,
  `DATABASE_URL` is a Cloudflare secret (`npx wrangler secret put
  DATABASE_URL` from `web/`; deploys as a Worker with static assets, not a
  classic Pages project, despite older docs saying "Cloudflare Pages").
- `DATABASE_URL`/`WIKTEXTRACT_DUMP`/`WIKTEXTRACT_DUMP_DATE` all default to
  the standard local dev DB and acquired-dump path in source (`db.ts`,
  `config.py`) -- `.env`/`.env.example` exist only to override one of
  them for a single machine. Never put a live Neon URL in `.env`; pass it
  inline for a one-off migration/backfill instead (`make db-apply
  DATABASE_URL=...`).
- The DB client is created **lazily** (`web/src/lib/server/db.ts`) so the
  build does not require `DATABASE_URL`. Keep it lazy.
- **cosmos.gl needs WebGL, which does not exist during SvelteKit's SSR
  render.** A static top-level `import { Graph } from '@cosmos.gl/graph'`
  in a `.svelte` file crashes every page load with
  `WebGL2RenderingContext is not defined`. Any component that renders a
  cosmos.gl canvas must import it lazily inside a browser-only function
  (an event handler, an `onMount`), never at module scope.
- **Local Postgres runs natively (no container), via `systemctl`.**
  Install `postgresql-server` as a native package (a layered rpm on an
  atomic/immutable Fedora variant), then
  `sudo postgresql-setup --initdb && sudo systemctl enable --now postgresql`.
  Fedora's default `pg_hba.conf` uses `ident` for TCP (`host`) connections,
  which rejects a `postgres://user:pass@localhost/...` DSN; change the
  `127.0.0.1/32`/`::1/128` `host` lines' method to `scram-sha-256` and
  `sudo systemctl reload postgresql` before a role can log in over TCP.
  Then create the `etymyriad` role/database matching `.env.example` via
  `sudo -u postgres psql`. `make db-up`/`db-down` just start/stop the
  `postgresql` service; `make db-apply`/`db-reset` talk to it directly
  with `psql`, no container involved.

## Project board & backlog workflow

The backlog, priorities, phase narrative, and open decisions all live on the
private [etymyriad GitHub Project](https://github.com/users/van-riper/projects/4)
(`gh project ... 4 --owner van-riper`) -- both its items and its README
field, which summarizes phase-by-phase progress and milestones. There is no
`docs/ROADMAP.md` anymore; that was a deliberate move (2026-07-15) to get
roadmap/backlog churn out of git history and PR diffs entirely.

Fields on every item: Status (Backlog/Ready/Blocked/In Progress/Done),
Type (Story/Bug/Task/Spike/Epic), Effort (XS/S/M/L/XL/XXL). Every item's
title carries an ETYM- prefix (e.g. `ETYM-42: ...`), one flat counter
shared across every Type - Epics aren't numbered separately.

For agents: see the `gh-triage` skill for field/option IDs and the
exact `gh project` commands -- this section stays conceptual, the skill
carries the mechanics. `gh project` reads (`view`/`list`/`item-list`/`field-list`) and
most writes (`item-create`/`item-edit`/`item-add`/`field-create`/
`item-archive`/`item-delete`) work from this repo. When you find
backlog-worthy work during a session (a bug, a missing feature, a
deferred decision) that isn't already tracked, add it as a draft item with
`gh project item-create 4 --owner van-riper --title "..." --body "..."`,
then set its Status/Type/Effort with `gh project item-edit`. New items
default to Status Backlog; Type/Effort have no default - state them
explicitly. Set Status to In Progress when you start non-trivial work,
Done once it ships. When a phase's coarse placeholder item starts
active work, split it into finer items and update the project README's
"Where things stand" note. Don't re-add churn-prone backlog or roadmap
detail back into `CLAUDE.md` -- the project board is the single source
of truth for what's left to do. Setting the README itself uses
`gh-triage`'s `scripts/set-readme.sh <readme-file>`. `field-delete` and
the project's title/visibility still have no wrapper and stay
`dcg`-blocked by the user's own choice -- hand those commands to the
user with `!` rather than asking.

For the user: new agent-created items land Status Backlog; triage by
raising Status when ready to pick up. Three views: Active (the default
Board, day-to-day kanban), Backlog (grooming/estimating table grouped
by Type), and Epics (table of `Type: Epic` items only, since an Epic's
Status reads as initiative progress rather than a unit of work) - see
the `gh-triage` skill's "Views" section for the exact filter/group/sort
per view, since `gh`/the GitHub API can't manage Project v2 Views.

## References

- `docs/DESIGN.md`: foundation design and rationale.
- Wiktextract / kaikki.org: <https://kaikki.org>
- Etymological Wordnet: validation source.
