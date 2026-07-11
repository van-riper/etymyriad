# etymyriad: Roadmap

_Last updated: 2026-07-10_

The plan from today's verified scaffold through a full-featured public tool.
Phases are roughly sequential, but the **walking skeleton** (Phase 0) and the
**data keystone** (Phase 1) gate everything else. Each later phase is mostly a
new _read_ over the same graph, which is the payoff of the data-model-first
design.

Legend: `[ ]` todo, `[~]` in progress, `[x]` done.

---

## Phase 0: Foundation & launch infrastructure (immediate)

Goal: a deployed "walking skeleton" so the whole path (repo -> CI -> Cloudflare
Pages -> etymyriad.com) is proven _before_ there is real logic to debug.

- [x] Repo scaffold, schema, dual license, design doc
- [x] Register etymyriad.com (Cloudflare)
- [x] Initial commit + `gh repo create etymyriad --public --source=. --push`
- [x] CI (GitHub Actions): etl (`uv sync`, `ruff format --check`,
      `ruff check`, `ty check`, `pytest`) + web (`npm ci`, `npm run check`,
      `npm run build`)
- [ ] Neon project + a `dev` branch, capturing the connection string
- [x] Cloudflare Pages project linked to the repo, auto-deploying on push to
      `main`
- [ ] `DATABASE_URL` set as a Pages secret (not yet needed: the deployed
      landing page doesn't touch the database)
- [x] Point etymyriad.com at the Pages project (DNS is in-house on Cloudflare)
- [x] Ship the placeholder landing page to production (first real deploy)

Milestone **M0 reached:** the stub site is live on etymyriad.com and every
push redeploys. Nothing about the graph yet, just a proven pipeline.

---

## Phase 1: Data ETL to the first real graph (the keystone)

Goal: a populated Postgres graph for Indo-European. This is the highest-value,
highest-risk work, and everything downstream reads from it.

- [x] **Acquire data:** kaikki.org deprecated its per-language exports (the
      source of the old `proto-germanic.jsonl`/`proto-indo-european.jsonl`
      samples) in favor of one combined dump covering every language.
      `data/raw/indo-european.jsonl` (gitignored, 8.3M entries / 443
      languages) now replaces them, produced by `etymyriad filter-ine`
      filtering the combined dump against a language list crawled from
      Wiktionary's own `Category:Indo-European languages`.
- [~] **Seed `language`:** `is_proto` is done, derived from the existing
      `-pro` code suffix (no external source needed, verified against the
      real dump with zero exceptions). `name`/`family` are still open --
      `load.py` never sees a human-readable name by the time it runs, so
      this needs either threading `entry["lang"]` through from `normalize`,
      or a separately sourced code -> name/family table.
- [x] **Implement `normalize._edges_from_entry`** (the core TODO): maps each
      entry's `etymology_templates` to `EtymEdge`s via `TEMPLATE_RELS`.
      Running it against the full real dump (not just curated fixtures)
      surfaced one live bug -- a same-word template self-reference
      (Portuguese "matreira") producing a self-loop edge -- fixed with a
      shared `_maybe_edge` guard across all four edge-emitting paths.
- [ ] ~~Validate~~ parser output against the Etymological Wordnet --
      **deliberately deferred**, not just pending. The 2013 EtymWN dump is
      itself mined from Wiktionary (same lineage, 13 years stale, not
      independent ground truth) and uses a different language-code scheme,
      so the effort-to-signal ratio lost to the ETL's 68 golden/unit tests.
      Revisit only if a concrete parser-correctness doubt surfaces that
      those tests can't settle.
- [~] **Load:** local podman Postgres is broken on at least one dev box
      (see `CLAUDE.md`'s Local-dev gotchas); a native `postgresql-server`
      install worked instead. A full real-data run loaded 3.19M edges /
      2.47M lexemes / 1.4GB locally with zero errors. Pushing the same
      dataset to Neon is in progress.
- [ ] **Data quality:** reconstructed-form handling is done
      (`is_reconstructed`/`is_proto`), and set-dedup + coalesce-upsert cover
      basic dedup. Homograph policy and orphan/cycle checks are still open --
      see the `bh` (Bihari/Bhojpuri) code collision under Open decisions.
- [ ] ETL reporting: entry/lexeme/edge counts, per-relation coverage. Each
      CLI subcommand already prints its own count; no per-relation-type
      breakdown yet.

Milestone **M1 reached (locally):** a recursive-CTE backtrace in `psql`
against the real loaded data returns `water` (en) -> `watōr` (gem-pro) ->
`wódr̥` (ine-pro), exactly the example this milestone named. Reaching M1
against Neon (not just local Postgres) is the remaining piece, since the
web app's Neon serverless driver can't talk to local Postgres at all.

---

## Phase 2: MVP graph explorer (public v1)

Goal: the core product. Search a word, see and explore its etymology network.

- [ ] Sigma.js + graphology canvas rendering the ego-network from
      `/api/word/:lang/:headword`
- [ ] Interactions: pan/zoom, **click-to-expand** a node's neighbors, focus
      switching
- [ ] Styling: color by language/family, edge style by `rel_type`, mark
      reconstructed forms
- [ ] **Anti-noise controls:** depth slider, relation-type filters, language
      filters, level-of-detail / clustering for dense nodes
- [ ] Word detail side panel (gloss, language, links, source citation)
- [ ] Search UX: autocomplete, language disambiguation for homographs
- [ ] Responsive layout, loading/empty/error states
- [ ] Deploy to production

Milestone **M2:** a stranger can visit etymyriad.com, search a word, and
explore its network smoothly. This is the portfolio-ready core.

---

## Phase 3: Word pages, backtraces, breakdowns (depth + SEO)

Goal: discoverable, linkable depth around each word. Each is a read over the
same schema.

- [ ] **Word breakdown pages** `/word/:lang/:headword`: canonical, shareable,
      SEO-friendly. Pre-render popular words (SSG), and render the long tail on
      demand via Pages Functions + cache.
- [ ] **Linear backtrace** endpoint + view: the ancestor chain for any word in
      any language (a primary requested feature).
- [ ] **Morphological breakdown:** decompose affixes / compounds / roots.
- [ ] **Descendants** view and **cognate explorer**.
- [ ] SEO: sitemap, meta tags, schema.org structured data, OpenGraph cards.
- [ ] Cross-linking between related word pages.

Milestone **M3:** Google can index "etymology of X" pages, and any word has a
permanent home with its backtrace and breakdown.

---

## Phase 4: Geography, the word-to-country map

Goal: see _where_ a word's lineage lives, on a map.

- [ ] Source language -> region/coordinate data (Glottolog coordinates, WALS).
- [ ] Map view (candidate: MapLibre GL, vector + WebGL) plotting the languages
      in a word's ancestry.
- [ ] Temporal dimension: proto-language eras, approximate dates.
- [ ] Optional: animate spread / migration of a root across regions and time.

Milestone **M4:** searching a word can show its origins geographically, not
just as a node graph.

---

## Phase 5: Breadth, performance, polish

Goal: scale data and audience.

- [ ] Expand beyond Indo-European to other families (the schema already
      supports it, so this is a data + performance exercise).
- [ ] Performance: precompute popular neighborhoods, edge/CDN caching, query
      tuning, pagination of dense nodes.
- [ ] Incremental re-ingestion of new Wiktextract dumps (idempotent loads).
- [ ] Accessibility pass, mobile polish, keyboard navigation.
- [ ] Privacy-respecting analytics, basic usage insight.
- [ ] Public dataset export (honoring CC BY-SA attribution + share-alike).

Milestone **M5:** broad coverage, fast everywhere, maintainable update loop.

---

## Phase 6: AI layer (deferred, optional)

Goal: natural-language access _over_ the sourced graph. AI never authors facts.

- [ ] Natural-language search: "Latin roots of English legal terms" -> a
      structured graph query.
- [ ] Prose summaries of a word's etymology, generated from the structured data
      with citations preserved.
- [ ] Optional: AI-assisted data cleaning during ingestion (human-reviewed).
- [ ] Guardrails: every surfaced fact traces to a `source_ref`, and the graph
      stays deterministic.

Milestone **M6:** ask a question in plain language, get an answer grounded in
the cited graph.

---

## Cross-cutting (ongoing from Phase 0)

- **Testing:** ETL unit tests (parsing, normalization), web component
  tests, an end-to-end smoke test on the deployed site.
- **CI/CD:** lint + type-check + test + build on every PR, auto-deploy on merge.
- **Provenance & licensing:** keep per-edge citations, surface attribution in
  the UI, and put CC BY-SA on any data export.
- **Docs:** keep `DESIGN.md`, `CLAUDE.md`, and this roadmap current, with one
  design doc per major feature.
- **Schema migrations:** plain ordered SQL now, adopting dbmate/atlas when the
  schema starts churning.

---

## Open decisions & risks (revisit per phase)

| Topic               | Question                                                                                          | Phase |
| ------------------- | ------------------------------------------------------------------------------------------------- | ----- |
| ~~Data extraction~~ | ~~How to slice IE-only from the full Wiktextract dump?~~ **Resolved:** match Wiktionary's own `lang` names, crawled from `Category:Indo-European languages` (`etymyriad filter-ine`). | 1     |
| Parser accuracy     | Wiktionary etymology prose is messy. How good is "good enough"? Deferred formal validation against Etymological Wordnet (see Phase 1); the 68-test golden/unit suite plus a clean full-dump run is the current bar. | 1     |
| Homographs          | Is `(lang, headword, gloss)` enough, or add `pos`/sense ids? Concrete case found: Wiktionary's `bh` code covers both Bihari and Bhojpuri, so same-headword/gloss words from each would collide. | 1     |
| Data volume         | Does the IE graph fit Neon's free tier comfortably? Real number now known: 3.19M edges / 2.47M lexemes is 1.4GB in Postgres locally. Plan for paid if Neon's free tier doesn't cover that. | 1, 5  |
| Word-page rendering | SSG popular + on-demand long tail vs full SSR, plus cache strategy.                               | 3     |
| Geo data            | Glottolog vs WALS vs Wikidata for language coordinates/eras.                                      | 4     |
| Map library         | MapLibre GL vs Leaflet.                                                                           | 4     |
| Precomputation      | When to precompute neighborhoods/centrality (possibly a Rust step).                               | 5     |
| AI scope            | If/when to add, cost, strict no-hallucinated-facts guardrail.                                     | 6     |

---

## Immediate next actions (in order)

M0 (Phase 0) is done, and M1 (Phase 1) is reached locally: the full
Indo-European dataset is acquired, `normalize._edges_from_entry` is
implemented and bug-fixed against real data, and a real 3.19M-edge graph is
loaded and backtrace-queryable in local Postgres. What's next:

1. Create the **Neon** project and wire `DATABASE_URL`, then load the same
   dataset there (in progress as of 2026-07-10) -- this is what actually
   unblocks frontend work, since the web app's Neon serverless driver
   cannot talk to local Postgres under any connection string.
2. Start Phase 2: wire the landing-page search to a Sigma.js canvas backed
   by `/api/word/:lang/:headword`, expecting real drafting/iteration as the
   UI surfaces backend gaps the two-sample-file era never would have.
3. Pick up Phase 1's remaining loose ends opportunistically (language
   `name`/`family` seeding, homograph natural-key revisit) rather than
   gating Phase 2 on them -- none of them force a schema or API shape
   change.
