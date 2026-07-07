# etymyriad: Roadmap

_Last updated: 2026-07-02_

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

- [~] **Acquire data:** `data/raw/proto-germanic.jsonl` and
      `data/raw/proto-indo-european.jsonl` are pulled from kaikki.org. Still
      need the rest of the IE language list, and to reconcile the per-family
      files with `.env.example`'s single `WIKTEXTRACT_DUMP` path (merge, or
      teach the ETL to read a directory).
- [ ] **Seed `language`:** real names + families for IE languages (incl.
      proto-languages). Candidate source: Glottolog / Wikidata.
- [ ] **Implement `normalize._edges_from_entry`** (the core TODO): map each
      entry's `etymology_templates` to `EtymEdge`s via `TEMPLATE_RELS`. Build
      the ancestor lexeme, attach `source_ref`. Test-first against real samples.
- [ ] **Validate** parser output against the Etymological Wordnet (precision /
      recall on a sample). Record coverage stats.
- [ ] **Load** into local podman Postgres, then push the dataset to Neon.
- [ ] **Data quality:** dedup, reconstructed-form handling, homograph policy,
      orphan/cycle checks.
- [ ] ETL reporting: entry/lexeme/edge counts, per-relation coverage.

Milestone **M1:** you can run a recursive-CTE backtrace in `psql` and get a
real ancestor chain (e.g. English _water_ -> Proto-Germanic -> Proto-IE).

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
| Data extraction     | How to slice IE-only from the full Wiktextract dump?                                              | 1     |
| Parser accuracy     | Wiktionary etymology prose is messy. How good is "good enough"? Validate vs Etymological Wordnet. | 1     |
| Homographs          | Is `(lang, headword, gloss)` enough, or add `pos`/sense ids?                                      | 1     |
| Data volume         | Does the IE graph fit Neon's free tier comfortably? Plan for paid if not.                         | 1, 5  |
| Word-page rendering | SSG popular + on-demand long tail vs full SSR, plus cache strategy.                               | 3     |
| Geo data            | Glottolog vs WALS vs Wikidata for language coordinates/eras.                                      | 4     |
| Map library         | MapLibre GL vs Leaflet.                                                                           | 4     |
| Precomputation      | When to precompute neighborhoods/centrality (possibly a Rust step).                               | 5     |
| AI scope            | If/when to add, cost, strict no-hallucinated-facts guardrail.                                     | 6     |

---

## Immediate next actions (in order)

Steps 1-5 are done: the repo is public, CI is green, Pages is deployed, and
the placeholder site is live at etymyriad.com (M0). What's next:

1. Create the **Neon** project and wire `DATABASE_URL` (local `.env` for the
   ETL, Pages secret for the web app once a route needs it).
2. Finish pulling the rest of the Wiktextract IE sample into `data/raw/`.
3. Write `normalize._edges_from_entry` test-first (Phase 1's core TODO).
