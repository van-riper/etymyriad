# Etymyriad: Roadmap

_Last updated: 2026-07-14_

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
- [x] A Neon project, `DATABASE_URL` wired to root `.env` (Neon was the
      original pick, superseded by CockroachDB Cloud 2026-07-11, then
      switched back 2026-07-13 once CockroachDB's per-write billing proved
      unworkable for a one-time bulk load; provisioned and reloaded)
- [x] Cloudflare Worker (static assets, not a classic Pages project)
      linked to the repo, auto-deploying on push to `main`
- [x] `DATABASE_URL` set as a Worker secret (`npx wrangler secret put
      DATABASE_URL`) -- the graph view now sits behind a landing page's
      Begin button, so a visit alone doesn't touch the database
- [x] Point etymyriad.com at the Worker (DNS is in-house on Cloudflare)
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
      or a separately sourced code -> name/family table. **Raised in
      priority, 2026-07-12:** Phase 2's language-name typeahead and any
      color-by-language-family option both need normalized names, not just
      raw Wiktionary codes -- no longer purely opportunistic.
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
      install worked instead. A full real-data run loaded 2.99M edges /
      2.08M lexemes locally with zero errors (numbers shifted slightly from
      the earlier 3.19M/2.47M after the UUID-key and sense-table schema
      change). Pushing the same dataset to CockroachDB Cloud turned out to
      be blocked by request-unit cost, not compatibility; the backend
      switched back to Neon 2026-07-13 -- see Open decisions.
- [x] **Data quality:** reconstructed-form handling is done
      (`is_reconstructed`/`is_proto`), set-dedup + coalesce-upsert cover
      basic dedup, and homographs now key on `etymology_number` instead of
      `gloss` (fixed 2026-07-10, `gloss`/`pos` moved to a `sense` table).
      Still open: whether the `bh` (Bihari/Bhojpuri) code collision needs
      `pos` added to the key too -- see Open decisions.
- [ ] ETL reporting: entry/lexeme/edge counts, per-relation coverage. Each
      CLI subcommand already prints its own count; no per-relation-type
      breakdown yet.

Milestone **M1 reached, locally and against Neon:** a recursive-CTE
backtrace returns `etymology` (en) -> `etymologia` (la) -> `ἐτυμολογία`
(grc) against both. The Neon load carries 2,075,078 lexemes, 2,993,290
edges, 1,604,538 senses, and 1,944 languages -- the same dataset as the
local Postgres load, now live in the cloud.

---

## Phase 2: MVP graph explorer (public v1)

Goal: the core product. Search a word, see and explore its etymology network.

- [x] Sigma.js + graphology canvas rendering the ego-network from
      `/api/word/:lang/:headword`, on a full-viewport layout with a
      jittered concentric-ring layout by hop distance from the focus node
- [~] Interactions: pan/zoom (Sigma default camera), clicking a node
      re-centers the ego-network on it (not an in-place expand), a
      random-word entry point (`/api/random`, optional language filter)
- [ ] **Hover preview:** re-centering on click is costly to undo without a
      permalink/URL-state feature (not yet built). A hover tooltip
      (headword, language, one-line gloss) lets a user preview a node
      before committing to the jump.
- [ ] **Visited-word trail + back button:** each click discards the prior
      ego-network with no visual record of the path taken. Add a small
      breadcrumb trail of recently visited words, plus a "back" button
      that returns to the previous word's ego-network (not just the
      browser's own back button, which has no state to return to yet).
- [ ] **Graph visual redesign** (user feedback, 2026-07-12): the current
      layout reads as generic force-directed noise, not a knowledge graph.
      Revisit with knowledge-graph/RAG-style visual conventions:
      - Bigger, more readable lexeme labels (current ones are too small).
      - Show a word's direct etymons (its ancestor chain) visually
        separated from its cognates/derivatives, instead of one
        undifferentiated ring per hop distance.
      - Edge styling by `rel_type` (all edges currently look identical
        apart from a text label).
      - Colorize nodes by a still-undecided factor -- language, language
        family, and relation type are candidates (see Open decisions).
      - Mark reconstructed forms (`is_reconstructed`) with the standard
        linguistic asterisk convention (e.g. `*leǵ-`), not just color.
      - A legend explaining node color and edge style, once the coloring
        factor above is decided -- otherwise the scheme is meaningless to
        a viewer.
- [ ] **Draggable, physics-based node movement** (user feedback,
      2026-07-12): let a user drag a node and have the rest of the graph
      respond fluidly, the way Obsidian.md's graph view does, instead of
      the current static jittered-ring layout. Likely needs Sigma's
      node-drag interaction plus a continuously-running force-directed
      layout (e.g. `graphology-layout-forceatlas2`, compatible with the
      existing graphology graph), not just a one-time layout pass.
- [ ] **Anti-noise controls:** a depth control, relation-type filters
      (checkbox/dropdown to show/hide specific `rel_type`s), language
      filters, level-of-detail / clustering for dense nodes -- depth is
      currently hardcoded to 2 and the ego-network always renders in full.
- [ ] **Word detail panel:** clicking a node should surface its etymology,
      part of speech, definition, and gender/form/etc, plus a link out to
      its Wiktionary source page (from the `source_ref` already carried
      per edge). Depends on resolving how this coexists with click-to-
      recenter (see Open decisions).
- [ ] **Etymon side panel** (user feedback, 2026-07-12): a small side
      panel showing the focused lexeme's direct etymons as a linear
      chain, or a diverging tree when it has more than one etymon, with
      each ancestor rendered as its own clickable node that re-centers
      the main graph. Overlaps with the word detail panel above and
      Phase 3's linear backtrace view -- decide whether this subsumes
      one or both (see Open decisions).
- [ ] **Search UX:** typeahead for both lexemes and language names/codes,
      plus language disambiguation for homographs. Language-name typeahead
      depends on Phase 1's language `name`/`family` seeding (item above).
- [ ] **Fuzzy "did you mean" fallback:** a failed headword lookup currently
      just 404s. Since search is the primary entry point, a typo is the
      most common failure mode -- suggest close matches (Postgres trigram
      or edit-distance against existing headwords) instead of a dead end.
- [ ] **Sitewide visual design:** the whole site, not just the graph
      canvas, needs a coherent, good-looking skin/theme -- currently plain
      unstyled HTML. Candidate themes: Flexoki, Nord, Atom (One
      Dark/One Light), Everforest. Also worth considering: Catppuccin,
      Gruvbox, Solarized, and Rosé Pine -- all ship matched light/dark
      pairs, which lines up with the light/dark schemes item below.
- [ ] **Light/dark color schemes** (user feedback, 2026-07-12): define an
      actual palette for both themes as part of the sitewide visual
      design work above, not just a toggle with no backing styles.
- [ ] **Dark/light mode toggle** (user feedback, 2026-07-12): a control
      cycling light/dark/follow-browser-setting (`prefers-color-scheme`),
      persisted across visits. Depends on the color schemes above
      existing to switch between.
- [~] Responsive layout, loading/empty/error states -- a plain error
      message exists for a failed search; no loading indicator yet
- [ ] **First-visit example:** a bare search box with no result gives no
      hint what to try. Show one worked example (e.g. a "try: etymology" chip
      that fires the search) as the default/empty state.
- [x] Deploy to production. Continuous auto-deploy has been live since
      Phase 0; the landing page, search, graph view, and random-word
      button all shipped in the `v0.1.0` release.

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

- [x] **Rate limit `/api/word` and `/api/random`.** Done via Cloudflare's
      native Workers Rate Limiting binding (`RL_API`, 20 req/60s per
      client IP, shared across both routes), enforced in
      `web/src/hooks.server.ts` and skipped in dev. See
      `docs/superpowers/specs/2026-07-14-rate-limiter-design.md`.
- [ ] **Split the rate-limit bucket per environment.** A 2026-07-14
      security review found that `wrangler.jsonc` declares no named
      environments, so a PR preview deploy is just another version of
      the same Worker with the identical `RL_API` binding and
      `namespace_id` -- preview and production traffic currently share
      one 20-req/60s budget. Accepted as-is for now (low-traffic
      portfolio project); revisit if preview testing and production
      traffic ever contend for the same budget in practice.
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
| ~~Homographs~~      | ~~Is `(lang, headword, gloss)` enough, or add `pos`/sense ids?~~ **Resolved 2026-07-10:** key on `etymology_number` instead, with `gloss`/`pos` moved to a `sense` table. Still open: whether Wiktionary's `bh` code (covering both Bihari and Bhojpuri) needs `pos` added too, since a same-headword/gloss word from each would still collide. | 1     |
| ~~Backend DB provider~~ | ~~CockroachDB Cloud vs Neon vs other Postgres-wire providers?~~ **Resolved 2026-07-13:** back to Neon. CockroachDB's per-write request-unit billing made the ~3M-edge bulk load cost several times the free-tier budget even after fixing the ETL's redundant-upsert bug; Neon bills by storage/compute-hours instead, with no per-write meter, estimated $1-3/month for the dataset's real 1.87 GB size. | 1, 5  |
| Changelog tooling   | ~~Which changelog generator?~~ **Resolved 2026-07-13:** git-cliff, over cocogitto/release-please/standard-version/semantic-release -- it's a pure renderer with no versioning opinions, matching the existing manual stage-tag-ff workflow. Deferred as YAGNI until more version tags exist: only one tag in flight isn't enough to judge a template. Still open: which template (custom vs. bundled `keepachangelog`/`scoped`/`detailed`). Work shelved in `dev`'s git stash ("changelog for 0.1.0"). | 0, 5  |
| Node coloring       | What factor should drive node color -- language, language family, relation type, something else? Raised 2026-07-12, not yet decided. | 2     |
| Click interaction   | Clicking a node currently re-centers the graph on it. New ask (2026-07-12) is for a click to also open a word-detail panel. Does a click do both, does recentering move to a separate action (e.g. a button in the panel), or does a single vs. double click distinguish them? | 2     |
| Etymon panel scope  | New ask (2026-07-12): a side panel showing the focused word's etymon chain/tree as clickable nodes. Does this replace the word-detail panel, sit alongside it, or absorb Phase 3's linear backtrace view outright? | 2, 3  |
| Word-page rendering | SSG popular + on-demand long tail vs full SSR, plus cache strategy.                               | 3     |
| Geo data            | Glottolog vs WALS vs Wikidata for language coordinates/eras.                                      | 4     |
| Map library         | MapLibre GL vs Leaflet.                                                                           | 4     |
| Precomputation      | When to precompute neighborhoods/centrality (possibly a Rust step).                               | 5     |
| AI scope            | If/when to add, cost, strict no-hallucinated-facts guardrail.                                     | 6     |

---

## Immediate next actions (in order)

M0 (Phase 0) is done, and M1 (Phase 1) is reached both locally and on
Neon: the full Indo-European dataset is acquired,
`normalize._edges_from_entry` is implemented and bug-fixed against real
data, and a real graph (2.99M edges locally; 2,993,290 edges / 2,075,078
lexemes on Neon) is loaded and backtrace-queryable in both. `v0.1.0` has
shipped: the landing page, search, graph view, random-word button, and
API rate limiter are all live in production. What's next:

1. Continue Phase 2: the graph visual redesign, anti-noise controls
   (depth, rel-type/language filters, level-of-detail), the word-detail
   panel, and typeahead search -- the graph view itself, random-word
   entry, and click-to-navigate already work, but 2026-07-12 feedback
   judged the current visuals inadequate and dense words still render
   unfiltered and unreadable.
2. Dedupe lexemes in-process before upserting (once per distinct lexeme,
   not once per edge occurrence) and add a resume checkpoint to
   `load.py`. No longer a release blocker now that Neon doesn't meter
   per write, but still worth doing: fewer redundant writes means a
   faster load and a smaller compute-hour bill.
3. Pick up Phase 1's remaining loose ends opportunistically (language
   `name`/`family` seeding) rather than gating Phase 2 on them -- it
   doesn't force a schema or API shape change.
