# CLAUDE.md

Guidance for Claude Code working in the **etymyriad** repository.

## What this is

etymyriad shows where words come from: pick a word and it draws a bounded family
tree of its ancestors and descendants, backed by a **sourced, citable** dataset.
The name is _etymology + myriad_ ("a myriad of word origins").

Audience: a portfolio/learning showcase that doubles as a public tool for
language enthusiasts, held to research-grade accuracy.

Full rationale for every foundational decision is in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Read it before proposing
architectural changes. [`docs/DESIGN.md`](docs/DESIGN.md) is the visual and
interaction guide for the current UI; read it before changing anything in `web/`
that users see.

## Current status

- The ETL loads the Indo-European subset of the Wiktextract dump, trimmed to
  the fields the parser reads (`data/etymyriad-data.jsonl`,
  gitignored, built by `filter`). `load` takes the dump date from the raw
  dump's file name, and every citation names it. kaikki.org serves only its
  latest dump, so `fetch-dump` keeps the dump you downloaded.
- Production runs on **Neon**; local dev runs on native Postgres. Query either
  database for row counts or for the dump date it holds, since both change with
  every reload.
- The primary UI is `/tree/[lang]/[headword]`: the focus word in the middle,
  ancestor and descendant generations layered by BFS depth, laid out
  deterministically with no physics.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §4. In short: the Python ETL
runs offline and only writes rows to Postgres, and the SvelteKit app is both the
frontend and the API, with `+server.ts` routes querying Postgres directly.

## Data model invariants (do not violate)

The model is a directed, provenance-carrying graph (`db/schema.sql`):

- **`term`** = a node (a headword in one language).
- **`edge`** = a directed edge, `src -> dst` meaning **ancestor -> descendant**.
- **Every edge carries an `anchor`** into the Wiktionary page that states it,
  and `source_ref()` derives its full citation from the generation's dump date.
  Nothing in the graph is unsourced. This is what makes the dataset citable.
- **A section is stored only where Wiktionary states it**; never guess one.
- **Never generate etymological facts with AI.** The graph is deterministic and
  sourced. AI (deferred) may later summarize or search over it, never author it.
- **Never render the whole graph.** Every view is a bounded slice around one
  focus word (`/tree`'s bounded BFS), never a fetch of the whole table. The
  browser only ever sees a focused slice.
- Edge direction matters: backtrace walks `dst -> src`, and descendants walk
  `src -> dst`. Traversals use Postgres recursive CTEs.

If you change `db/schema.sql`, update `etl/src/etymyriad/model.py`, the loader's
DDL in `etl/src/etymyriad/load/`, `web/src/lib/shared/types.ts`, and
`db/migrations/0001_baseline.sql` to match. The baseline must stay identical to
`schema.sql`; a test enforces it.

## Tech stack and locked decisions

Do not relitigate these without a reason. They were chosen deliberately.

| Area        | Choice                         | Why                                                            |
| ----------- | ------------------------------ | -------------------------------------------------------------- |
| v1 scope    | Indo-European family           | Best Wiktionary coverage, richest chains.                      |
| Data source | Wiktextract / kaikki.org       | Machine-readable, cited.                                       |
| ETL         | Python 3.13 (uv)               | Wiktextract is Python. Best data/NLP ecosystem.                |
| DB          | **Neon** (serverless Postgres) | Recursive CTEs for traversal                                   |
| App + API   | **SvelteKit** (TypeScript)     | One codebase, shared types. Server routes are the API.         |
| Tree render | SVG + d3-hierarchy + d3-zoom   | Bounded slice, deterministic layout, no physics.               |
| Hosting     | **Cloudflare Workers** + Neon  | `adapter-cloudflare`, deployed as a Worker with static assets. |
| Domain      | etymyriad.com                  | Matches repo = package = domain.                               |
| AI          | Deferred                       | Designed-for, not built.                                       |

## Conventions

Python is uv-managed with **ruff** (`ruff format`, `ruff check`) at 80 cols, src
layout. Keep ETL dependencies minimal and justify each addition in the PR.
Before committing ETL changes, run `make etl-lint etl-ty etl-cov`.
TypeScript/Svelte uses 2-space indentation and must keep `svelte-check` clean,
with server-only code confined to `lib/server/`. The Pythonicator canon is the
primary source for Python style, while the Google Python style guide is a
fallback. The Google TypeScript style guide is the definitive baseline for
Typescript.

**Commits:** Conventional Commits. End commit messages with the coauthor
trailer, except version-bump commits (`chore: bump to vX.Y.Z`): those are run by
the user via `make release-bump-commit`, not authored by Claude, and carry no
trailer. Branch off `main` for feature work and merge back into `main` when
done. There is no `dev` branch. A release is a `v*` tag on `main`, so `main`
may be ahead of the latest release.

**Changelog:** `CHANGELOG.md` is generated from Conventional Commits by
[git-cliff](https://git-cliff.org)'s bundled `keepachangelog` config, no local
`cliff.toml`, since the built-in preset already matches this repo's history
exactly. `make release-bump VERSION=vX.Y.Z` regenerates it, bumps the
`etl`/`web` versions and their lockfiles, and stages the lot;
`make release-bump-commit VERSION=vX.Y.Z` does the same and also commits it as
`chore: bump to vX.Y.Z` and tags it (see Common commands). There are no GitHub
Releases, but pushing a `v*` tag that is on `main` deploys the site
(`.github/workflows/cd.yml`).

**General:** concise explanations, prefer composition over inheritance, show the
verify command for changes.

**Development discipline (TDD):** All feature work and bugfixes in this repo go
through test-driven development. Write the failing test first, watch it fail for
the right reason, then write the minimal code to pass, then refactor. The Iron
Law holds: no production code without a failing test first. Code written before
its test gets deleted and rewritten from the test, not adapted in place. This
covers the ETL (`uv run pytest`) and the web app (`npm run check` plus vitest);
a `svelte-check` error counts as a failing test. Narrow exceptions (throwaway
spikes, generated code, pure config) need a heads-up first, never a silent skip.
A golden-test divergence is a parser bug: fix the parser, never edit the golden
value to match buggy output. Browser-driven verification for `web/` changes goes
through the checked-in Playwright harness (`web/e2e/`, `npm run test:e2e`; see
the `verify` skill), never a throwaway script in `/tmp`. An interaction worth
checking once is usually worth keeping: add it as a spec in `web/e2e/` rather
than discarding it after a one-off manual check.

## Common commands

```sh
# Database (local dev, native Postgres via systemctl); `make help` lists all
make db-up         # start local Postgres
make db-down       # stop local Postgres
make db-init       # create the local role and database (one-time)
make db-apply      # create the schema in an empty $DATABASE_URL
make db-grant-web  # read-only grants for web_readonly (once per DB)
make db-psql       # psql shell
make db-reset      # drop everything in the local DB, then db-apply
make db-snapshot   # dump the local DB to db/snapshot.dump (gitignored)
make db-restore    # replace the local DB with db/snapshot.dump

# ETL (Python)
cd etl && uv sync
uv run pytest
uv run ruff check        # lint
uv run ruff format       # format
uv run ty check          # type-check
uv run etymyriad fetch-dump  # download the raw dump to data/ unless it
                             # is there; prints the path
uv run etymyriad filter --input ../data/wiktextract-data-YYYY-MM-DD.jsonl.gz
                             # scope + trim -> data/; `all` runs
                             # fetch-dump and this itself
uv run etymyriad parse       # inspect the dump
uv run etymyriad sync-languages  # refresh languages/registry.json
                                  # from Wiktionary + Wikidata; once per
                                  # dump refresh, then commit the diff
uv run etymyriad normalize   # filtered dump ->
                              # data/etymyriad-edges.jsonl; run once per
                              # dump or parser change
# load and crosscheck take the dump date from the raw dump's file name; all
# and fetch-dump read kaikki.org, so they need network access
uv run etymyriad load        # the edge file -> Postgres; run freely.
                              # --skip-sanity-gate lets a load past the
                              # 10% count-drift gate
uv run etymyriad all         # normalize + load; reuses the edge file
                              # unless the dump is newer. --force-normalize
                              # re-parses, for a genuine parser change
# Neon reloads run as the "ETL" GitHub Actions workflow (manual).

# Web (frontend + API)
cd web && npm install
npm run dev        # local dev server
npm run check      # svelte-check (must be clean)
npm test           # vitest; *.db.test.ts files need the loaded local DB
npm run test:unit  # vitest without the DB tests (what CI runs)
npm run test:e2e   # Playwright e2e specs (web/e2e/), against a real dev server + DB
npm run build      # production build via Cloudflare adapter

# Release (bump + tag)
make release-bump VERSION=vX.Y.Z         # changelog + etl/web versions + lockfiles, staged only
make release-bump-commit VERSION=vX.Y.Z  # same, plus commit + tag, on main
git push origin main vX.Y.Z              # the tag deploys production
```

## Local-dev gotchas

- **Repairing a broken DB rarely needs a full reload.** Re-run `normalize` only
  when a parser or normalizer fix has to reprocess the raw dump. Otherwise:
  - On Neon, `production` keeps 6h of history (`history_retention_seconds`).
    Restore or branch from a timestamp before the bad write in the Neon console
    or with the MCP tools.
  - Locally, run `make db-snapshot` after a known-good load, and
    `make db-restore` later rewinds to it without re-parsing the dump.

  Both only rewind. To apply a fix, re-run `etymyriad load`, which builds the
  graph in a fresh `loading` schema and swaps it in.

- **System Python is 3.14**, too new for some data-lib wheels. The ETL is pinned
  to **3.13** via `etl/.python-version`, and uv fetches it automatically. Do not
  "upgrade" this without checking wheel availability.
- **The Neon serverless driver talks HTTP only to Neon's own endpoint, never to
  a plain local Postgres**, `Pool`/`Client` included, since those still go
  through Neon's WebSocket proxy. `web/src/lib/server/db.ts` resolves this with
  a dev/prod split: dev dynamically imports the `postgres` package for a real
  TCP connection to local Postgres; prod keeps `neon()` for the Cloudflare
  Workers runtime, which can't open raw TCP sockets. In prod, `DATABASE_URL` is
  a Cloudflare secret (`npx wrangler secret put DATABASE_URL` from `web/`) for
  the read-only `web_readonly` role, never the owner.
- `DATABASE_URL` defaults to the standard local dev DB in source (`db.ts`,
  `config.py`), and every ETL reader reads `data/etymyriad-data.jsonl`.
  `.env`/`.env.example` exist only to override `DATABASE_URL` for a single
  machine.
  Never put a live Neon URL in `.env`; pass it inline for a one-off command
  instead (`DATABASE_URL=... uv run etymyriad load`).
- The DB client is created **lazily** (`web/src/lib/server/db.ts`) so the build
  does not require `DATABASE_URL`. Keep it lazy.
- **A migration that adds a column to live tables must backfill it.**
  `ALTER TABLE ... ADD COLUMN ... DEFAULT FALSE` writes `false` into every
  existing row, and nothing recomputes it until the next reload. Migration 0007
  did this to `is_redlink` on Neon and marked ~534K genuine redlinks as real
  entries. Ship the query that computes the true value in the same migration.
- **Local Postgres runs natively (no container), via `systemctl`.** Install
  `postgresql-server` as a native package (a layered rpm on an atomic/immutable
  Fedora variant), then
  `sudo postgresql-setup --initdb && sudo systemctl enable --now postgresql`.
  Fedora's default `pg_hba.conf` uses `ident` for TCP (`host`) connections,
  which rejects a `postgres://user:pass@localhost/...` DSN; change the
  `127.0.0.1/32`/`::1/128` `host` lines' method to `scram-sha-256` and
  `sudo systemctl reload postgresql` before a role can log in over TCP. Then run
  `make db-init` to create the `etymyriad` role and database.
  `make db-up`/`db-down` start and stop the `postgresql` service.
- **A reload drops the previous generation at the swap.** Roll back through
  Neon's 6h instant restore, or reload the previous dump.

## Project board & backlog workflow

The backlog, priorities, phase narrative, and open decisions all live on the
private
[etymyriad GitHub Project](https://github.com/users/van-riper/projects/4)
(`gh project ... 4 --owner van-riper`): both its items and its README field,
which summarizes phase-by-phase progress and milestones. There is no
`docs/ROADMAP.md` anymore; that was a deliberate move (2026-07-15) to get
roadmap/backlog churn out of git history and PR diffs entirely.

Fields on every item: Status (Backlog/Ready/Blocked/In Progress/Done), Type
(Story/Bug/Task/Spike/Epic), Effort (XS/S/M/L/XL/XXL). Every item's title
carries an ETYM- prefix (e.g. `ETYM-42: ...`), one flat counter shared across
every Type - Epics aren't numbered separately.

For agents: see the `gh-triage` skill for field/option IDs and the exact
`gh project` commands. This section stays conceptual, and the skill carries the
mechanics. `gh project` reads (`view`/`list`/`item-list`/`field-list`) and most
writes (`item-create`/`item-edit`/`item-add`/`field-create`/
`item-archive`/`item-delete`) work from this repo. When you find backlog-worthy
work during a session (a bug, a missing feature, a deferred decision) that isn't
already tracked, add it as a draft item with
`gh project item-create 4 --owner van-riper --title "..." --body "..."`, then
set its Status/Type/Effort with `gh project item-edit`. New items default to
Status Backlog; Type/Effort have no default - state them explicitly. Set Status
to In Progress when you start non-trivial work, Done once it ships. When a
phase's coarse placeholder item starts active work, split it into finer items
and update the project README's "Where things stand" note. Don't re-add
churn-prone backlog or roadmap detail back into `CLAUDE.md`: the project board
is the single source of truth for what's left to do. Setting the README itself
uses `gh-triage`'s `scripts/set-readme.sh <readme-file>`. `field-delete` and the
project's title/visibility still have no wrapper and stay `dcg`-blocked by the
user's own choice, so hand those commands to the user with `!` rather than
asking.

For the user: new agent-created items land Status Backlog; triage by raising
Status when ready to pick up. Three views: Active (the default Board, day-to-day
kanban), Backlog (grooming/estimating table grouped by Type), and Epics (table
of `Type: Epic` items only, since an Epic's Status reads as initiative progress
rather than a unit of work) - see the `gh-triage` skill's "Views" section for
the exact filter/group/sort per view, since `gh`/the GitHub API can't manage
Project v2 Views.

## References

- `docs/ARCHITECTURE.md`: foundation design and rationale.
- `docs/DESIGN.md`: visual and interaction guide for the current UI.
- Wiktextract / kaikki.org: <https://kaikki.org>
