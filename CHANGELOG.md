# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.12] - 2026-09-04

### Added

- Add the Canceled gh-triage status option id
- Add prettier format check

### Changed

- Drop cross-link edges
- Fold diacritic redlink stubs
- Drop ticket refs from comments
- Drop double-hyphen dashes in comments
- Load Inter and script fallback fonts
- Satisfy prettier check
- Bump to v0.4.12

### Fixed

- Fit the pre-hydration paint
- Keep an empty etym key in the URL
- Resolve abandoning by etym key
- Split affix piece lang: prefixes
- Hide unbrowsable langs in search
- Visible labels for search boxes
- Split dotted Latin shorthand terms
- Fix tree fixtures after diacritic merge

## [0.4.11] - 2026-09-03

### Added

- Add timestamp to logs
- Add inflection relation type

### Changed

- Rank inflection as lineage priority
- Extract inflection candidate spool
- Split form-of dst from homograph
- Bump to v0.4.11

### Fixed

- Restore is_redlink on edges.jsonl read
- Pin tab title to focus word
- Fold senseless split-headword siblings
- Emit inflection edges for cited forms
- Drop own etymology on form-of pages
- Guard concurrent load_edges runs
- Swap lock_timeout under contention

### Removed

- Remove ancestor/descendant depth cap

## [0.4.10] - 2026-09-02

### Added

- Add migration dropping loaded_at

### Changed

- Reuse edges.jsonl in all
- Move pg_trgm to ext, drop loaded_at
- Stream edges into COPY staging tables
- Rebuild loading, defer bulk indexes
- Merge staged keys into final tables
- Drop cross-run purge machinery
- Rebuild deferred indexes in bulk
- Sanitize rebuild indexes docstring
- Atomic schema swap and rollback
- Wire blue/green load_edges pipeline
- Drop --checkpoint arg
- Drop checkpoints and shrink timeout
- Guard the reload's silent failure modes
- Cap the schema swap's lock wait
- Trim loader SQL and stale docs
- Give the reload more timeout headroom
- Note migration 0010 and reload storage cost
- Split load into a package
- Tidy up pyproject.toml
- Bump to v0.4.10

### Fixed

- Drop ticket ref, fix docstring lint
- Satisfy ty, drop task refs
- Drop task reference, reflow comment
- Guard stub-fold against duplicate edges
- Verify --debug sets logging level
- Index before the post-merge fixups
- Surface real loader debug logs
- Mirror tests/ layout on src/
- Drop tests/ __init__.py, silence rule
- Recreate pg_trgm in ext on Neon

## [0.4.9] - 2026-08-28

### Added

- Add _WiktextractEntry.first_gloss
- Add manual full-reload workflow for Neon
- Add cd workflow, gate on version tag

### Changed

- Show selected lexeme in tab title
- Move natural_key onto Lexeme
- Split normalize into a package
- Guard cd deploy to main-only tags
- Drop DrL layout for lexeme.degree
- Refresh DESIGN.md for lexeme.degree
- Report disk space during reload job
- Bump to v0.4.9

### Fixed

- Merge split-headword ancestor stubs
- Drop mention edges from tree walk
- Re-home tied-depth lineage ancestors
- Load entries with no ancestor edges
- Exclude isolated nodes from random pick
- Give redlink fixture a layout row
- Comma-format large counts in CLI
- Bump server test timeout
- Comma-format edge count in normalize log
- Repair etl reload job after layout drop

### Removed

- Remove applied backfill scripts

## [0.4.8] - 2026-08-24

### Added

- Add surf +type-flag stub backfill

### Changed

- Validate wiktextract with pydantic
- Record and-latch migration hazard
- Swap LanguageCombobox to bits-ui
- Harden legend popover with bits-ui
- Dismiss homograph picker on Escape
- Revert detail-card override on Escape
- Swap search-bar labels for icons
- Sync README with /tree pivot
- Mark /tree as built in CLAUDE.md
- Sync DESIGN.md with /tree pivot
- Purge stale comments and ticket refs
- Directional edges with rel labels
- Curve edges, round cross-links
- Rounded, color-coded edge labels
- Apply prettier formatting
- Extract _af_extra_terms helper
- Purge stale rows after full load
- Bump to v0.4.8

### Fixed

- Fix stale e2e dataset fixtures
- Skip malformed entries in normalize
- Re-measure size via ResizeObserver
- Stop surf +type flag as language
- Reconcile surf edges by source_ref
- Converge surf reconciliation fully
- Widen rows, align edge arrows
- Disable cross-link edges
- Expect no cross-link render
- Read etymon af pieces past 4

## [0.4.7] - 2026-08-17

### Added

- Add themed root error page
- Add lexeme.is_redlink flag
- Add fast local DB repair path

### Changed

- Pin trailingSlash explicitly
- Harden /api/* errors and headers
- Exclude and flag redlink lexemes
- Use rule names in per-file ignores
- Use ruff: ignore, named rule codes
- Bump ruff floor to >=0.16
- Bump to v0.4.7

### Fixed

- Unify API errors on message field
- Cover hardened HTTP error handling
- Map {{surf}} to surface_analysis
- Stop dropping surface_analysis edges
- Clear redlinks across etym splits

## [0.4.6] - 2026-08-07

### Changed

- Size tree nodes to fit their label
- Icon-based theme toggle
- Split treeLayout into submodule
- Move shared files to lib/shared/
- Move theme files to lib/theme/
- Move language files to lib/
- Move tree feature into lib/tree/
- Update CLAUDE.md for new lib/ layout
- Empty-state landing card
- Bump to v0.4.6

### Fixed

- Dblclick to navigate in tree e2e spec
- Tiny-tree ceiling ignores stroke
- Route cross-links around nodes
- Route cross-links around tree edges
- Format drift and stale skill reference
- Flexoki-theme toast notifications
- Default empty lang box to en

## [0.4.5] - 2026-08-07

### Added

- Add svelte-sonner toasts
- Add web-test-e2e, web-format, etl-ty targets
- Add web-dev-start/-stop/-logs targets

### Changed

- Split tree click vs dblclick
- Toast when a tree is too large to fit
- Route fetches through apiFetch
- Delay-gate the loading spinner
- Drop unused compose.yaml
- Run vitest in the web workflow
- Run prettier --write on drifted files
- Check prettier formatting in web-lint
- Ci: run vitest in the web workflow
- Bump to v0.4.5

### Fixed

- Cap render scale for tiny trees
- Lower tiny-tree render-scale ceiling
- Stop crashing on a bad lexemes reply
- Mount Toaster before page content
- Guard bump instead of unstaging

## [0.4.4] - 2026-08-06

### Added

- Add etymology.piece_order column
- Add tree legend for edge conventions

### Changed

- Scaffold playwright e2e harness
- Document e2e test workflow
- Thread piece_order through edges
- Order composed siblings by piece order
- Select piece_order in tree walk queries
- Default DATABASE_URL to local Postgres
- Default WIKTEXTRACT_DUMP, drop .env files
- Reuse e2e harness, drop /tmp tests
- Bump to v0.4.4

### Fixed

- Make piece-order sort transitive
- Set piece_order on etymon :af pairs
- Broaden e2e coverage past smoke
- Exclude e2e specs from vitest
- Default-stub fetch in jsdom

## [0.4.3] - 2026-08-05

### Added

- Add dash-placeholder stub backfill

### Changed

- Pan/zoom the tree canvas
- Cap sibling fan-out per parent
- Reveal capped siblings on click
- Keep most relevant capped siblings
- Bump to v0.4.3

### Fixed

- Cap tree fetch to what's rendered
- Treat literal "-" as no term arg

## [0.4.2] - 2026-08-05

### Added

- Add server-side wiktionary proxy
- Add affix-dash stub backfill

### Changed

- Asterisk-mark reconstructed headwords
- Bump to v0.4.2

### Fixed

- Fix eslint config on fresh checkouts
- Match affix siblings by senses

## [0.4.1] - 2026-08-05

### Changed

- Merge landing/tree into one shell
- Bump to v0.4.1

### Fixed

- Restore implied dash on affix pieces
- Center tree diagram and search bar
- Wire eslint into web-check/CI
- Satisfy no-navigation-without-resolve

### Removed

- Remove cosmos.gl dependency

## [0.4.0] - 2026-08-04

### Added

- Add bounded ancestor/descendant query
- Add d3-hierarchy dependency
- Add treeLayout for a lone focus node
- Add TreeDiagram genealogy renderer
- Add slash-safe tree URL builder
- Add /tree search and refocus

### Changed

- Retire /graph viewport tiling
- Resolve headword to lexeme id
- Modularize lib
- Lay out ancestors via d3-hierarchy
- Bump to v0.4.0

### Fixed

- Cover ancestor/descendant merge
- Cover rel_type parent tie-break
- Cover duplicate-edge collapsing
- Cover diamond, siblings, viewBox
- Cover TreeDiagram node click
- Cover TreeDiagram edge kind classes
- Harden tree layout edge cases
- Repoint homepage search at /tree

### Removed

- Remove dead /graph route

## [0.3.0] - 2026-08-02

### Added

- Add cosmos.gl frontend dependency

### Changed

- Shape buildGraph for cosmos.gl
- Render the graph page via cosmos.gl
- Reflect cosmos.gl in place of sigma.js
- Bump to v0.3.0

### Fixed

- Stop cosmos.gl point drift
- Stop cosmos canvas growth loop
- Stop full rebuild on search-box typing

### Removed

- Remove sigma.js and graphology

## [0.2.5] - 2026-08-01

### Added

- Add component-test harness

### Changed

- Backfill leaked-annotation lexemes
- Loading, empty, and error state polish
- Bump to v0.2.5

### Fixed

- Raise rate limit, pool globally
- Strip <id:> tags from affix/der/m nodes
- Map Latin-period editor shorthand
- Strip PUA markers from headwords
- Hide center button until graph loads
- Merge senseless bound-morpheme stubs
- Hide senseless stub from picker

## [0.2.4] - 2026-08-01

### Added

- Add make db-init for local role/db
- Add community-vs-family spike script
- Add backbone-filter spike script

### Changed

- Update Claude Code enabled plugins
- Disambiguate homographs in search
- Bump to v0.2.4

### Fixed

- Verify DrL layout convergence
- Freeze picker word while typing
- Enter in lang box now submits search

## [0.2.3] - 2026-07-23

### Added

- Add language list API endpoint
- Add language typeahead combobox
- Add center button to graph canvas

### Changed

- Join language name into lexeme detail
- Show lexeme detail in side panel
- Rank languages for typeahead search
- Guard against empty lang code
- Guard against empty headword
- Bump to v0.2.3

### Fixed

- Refresh language on reupsert
- Stop mangling ancestor language codes
- Resize graph canvas on panel toggle
- Resolve nav links per eslint rule
- Keep collapse toggle x position

## [0.2.2] - 2026-07-23

### Added

- Add N= node-count readout
- Add collapse toggle to side panel

### Changed

- Move top bar into a left side panel
- Swap random lang filter for checkbox
- Bump to v0.2.2

### Fixed

- Drop stray CSS/aria polish items

## [0.2.1] - 2026-07-23

### Changed

- Note viewport minDegree=0 caveat
- Drop podman, add reset confirm
- Bump to v0.2.1

### Fixed

- 404 malformed lexeme ids, not 500
- Dedupe hover/click lexeme fetches
- Guard loadNetwork against stale nav
- Skip empty gloss in hover tooltip

## [0.2.0] - 2026-07-22

### Added

- Add GiST spatial index for viewports
- Add viewportTile query
- Add GET /api/viewport route
- Add lexemePosition query
- Add lexemeDetail query
- Add /api/position route
- Add /api/lexeme/:id route

### Changed

- Rank lexemes by degree in layout job
- Update .gitignore
- Log progress in the layout job
- Adopt pythonicator canon ruff config
- Binary wire format for viewport tile
- Format lexemeDetail query and header
- Render viewport tiles, not rings
- Sync status with viewport renderer
- Replace stale ego-network query
- Rewrite anti-noise design for viewport tiles
- Bump to v0.2.0

### Fixed

- Shrink viewport test to a real tile
- Distinct viewport error + hover cleanup
- Cap viewport tile node count
- Fix spatial-index test drift
- Fix stale ego-network wording in comments
- Fix verify skill for viewport changes

### Removed

- Delete retired ego-network code
- Remove orphaned DEFAULT_DEPTH constant

## [0.1.9] - 2026-07-21

### Added

- Add lexeme_layout table
- Add python-igraph dependency
- Add fetch_graph for layout batch job
- Add compute_layout via igraph DrL
- Add write_layout upsert
- Add etymyriad layout subcommand

### Changed

- Rename conn/cur to connection/cursor
- Apply pythonic-canon findings
- Bump to v0.1.9

### Fixed

- Satisfy ruff/ty on layout module
- Fold bump commit into own changelog

### Removed

- Remove site color button from landing page for now

## [0.1.8] - 2026-07-21

### Added

- Add Flexoki theme tokens
- Add reactive theme state module
- Add theme toggle button
- Add attribution to Flexoki in README

### Changed

- Swap project-backlog for gh-triage plugin
- Set data-theme before first paint
- Wire root layout to the theme module
- Theme-aware ego-network node colors
- Re-theme the ego-network canvas live
- Theme the landing page and badges
- Bump to v0.1.8

### Fixed

- Guard against stale renderNetwork calls
- Relocate site color button
- Apply theme styling for text boxes

### Removed

- Remove tool permissions path

## [0.1.7] - 2026-07-17

### Added

- Add git-cliff changelog make target
- Add web-check/web-build, preflight targets
- Support new fields in item scripts
- Add board-summary.sh
- Add search-before-create step
- Add landing search form
- Add /graph/[lang]/[headword] route
- Add claude settings and gitignore lines

### Changed

- Split make bump into stage/commit targets
- Rename and reorganize Makefile targets
- Wrap project-backlog gh calls in scripts
- Update lib.sh for board schema
- Describe the new backlog field schema
- Externalize board config
- Note the externalized config file
- Extract Badges into component
- Make landing page search-only
- Bump to v0.1.7

### Fixed

- Point refresh-ids.sh at conf file
- Shrink text boxes, polish search form

## [0.1.6] - 2026-07-16

### Added

- Add batch create_item snippet

### Changed

- Run etl coverage explicitly in test step
- Bump to v0.1.6

### Fixed

- Dedupe Path parse in _read_checkpoint
- Rename sub to subparsers in CLI parser
- Make language lookup tables read-only
- Parametrize duplicate upsert tests
- Parametrize is_indo_european tests
- Stop always running coverage in pytest

## [0.1.5] - 2026-07-16

### Added

- Add GitHub repo link icon
- Add author credit to landing page

### Changed

- Seed lang_family for IE languages
- Bump to v0.1.5

## [0.1.4] - 2026-07-16

### Added

- Add progress logging to load command
- Add --debug CLI flag

### Changed

- Report edge counts by rel_type
- Bump to v0.1.4

## [0.1.3] - 2026-07-15

### Added

- Add strict robots.txt for pre-launch

### Changed

- Group language modules in a package
- Mirror languages/ package in tests/
- Dedupe lexemes, add resume checkpoint
- Bump to v0.1.3

### Fixed

- Number backlog items sequentially

## [0.1.2] - 2026-07-15

### Added

- Add project-backlog skill

### Changed

- Wire logo as SVG favicon
- Move roadmap/backlog to GitHub Project
- Seed language table with real names
- Trim bh docstring in language_names.py
- Document version bump steps in README
- Bump to v0.1.2

### Removed

- Remove unused __version__

## [0.1.1] - 2026-07-14

### Added

- Add rate-limit response helper
- Add theme candidates, rate-limit bucket note

### Changed

- Wire RL_API rate-limiting binding
- Rate-limit /api/* per client IP
- Mark the API rate limiter done
- Reconcile roadmap with shipped v0.1.0 state
- Bump to v0.1.1

### Fixed

- Fix branching guidance to use dev

## [0.1.0] - 2026-07-13

### Added

- Add coming-soon landing placeholder (#1)
- Add cloudflare worker deploy config (#2)
- Add pytest-postgresql db harness
- Add edge JSONL intermediate
- Add normalize and load subcommands
- Add a filter-ie CLI step for the combined Wiktextract dump
- Add project verify skill for headless-browser checks
- Add a random-word button to the search bar
- Add a language filter to the random button
- Add UI/UX and rate-limit backlog items
- Add theming and etymon-panel backlog items
- Add centered site title to top bar
- Add a landing page with a Begin button

### Changed

- Scaffold etymyriad foundation
- Disable default workers.dev url (#3)
- Align style with Google's convention (#4)
- Sync roadmap and CLAUDE.md with reality
- Move ruff.toml into pipeline/
- Rename pipeline/ to etl/
- Source and normalize lexemes
- Require non-empty source_ref
- Coalesce lexeme upserts on conflict
- Skip malformed JSONL lines
- Redact DSN passwords
- Pin dump date via WIKTEXTRACT_DUMP_DATE
- Parse directional etymology templates
- Parse the etymon template
- Parse affix and mention templates
- Put pg_ctl where tests expect it
- Sharpen types and naming
- Chunk and pipeline the loader's upserts
- Seed is_proto when loading languages
- Reconcile status docs with real progress
- Frontend graph view v1
- Log write_edges progress every 100k edges
- Click a node to navigate the graph to it
- Run CI on push to dev
- Scatter ego-network nodes into jittered, scaled rings
- Make the graph canvas fill the screen
- Push random controls to the right of the top bar
- Hide page-level scrollbar
- Refresh stale docs, expand roadmap
- Rename example word water to etymology
- Replace underwater example with reverse
- Capitalize "Etymyriad" site/doc titles
- Switch backend provider docs to Neon
- Reorder and unpin pytest-postgresql dep
- Mark DATABASE_URL as a live Pages secret
- Note deferred changelog tooling decision
- Show the app version in the corner

### Fixed

- Lock in the no-edge template set
- Close the DSN leak guard's remaining gaps
- Lock RelType to the etym_rel_type SQL enum
- Lock set-dedup for Lexeme and EtymEdge
- Rename filter-ie to filter-ine
- Avoid same-word self-loop edges
- Cockroachdb-compatible schema
- Key lexemes on etymology_number, not gloss
- Use UUID keys, not sequential IDENTITY

### Removed

- Remove .claude/ tooling scaffold

[0.4.12]: https://github.com/van-riper/etymyriad/compare/v0.4.11..v0.4.12
[0.4.11]: https://github.com/van-riper/etymyriad/compare/v0.4.10..v0.4.11
[0.4.10]: https://github.com/van-riper/etymyriad/compare/v0.4.9..v0.4.10
[0.4.9]: https://github.com/van-riper/etymyriad/compare/v0.4.8..v0.4.9
[0.4.8]: https://github.com/van-riper/etymyriad/compare/v0.4.7..v0.4.8
[0.4.7]: https://github.com/van-riper/etymyriad/compare/v0.4.6..v0.4.7
[0.4.6]: https://github.com/van-riper/etymyriad/compare/v0.4.5..v0.4.6
[0.4.5]: https://github.com/van-riper/etymyriad/compare/v0.4.4..v0.4.5
[0.4.4]: https://github.com/van-riper/etymyriad/compare/v0.4.3..v0.4.4
[0.4.3]: https://github.com/van-riper/etymyriad/compare/v0.4.2..v0.4.3
[0.4.2]: https://github.com/van-riper/etymyriad/compare/v0.4.1..v0.4.2
[0.4.1]: https://github.com/van-riper/etymyriad/compare/v0.4.0..v0.4.1
[0.4.0]: https://github.com/van-riper/etymyriad/compare/v0.3.0..v0.4.0
[0.3.0]: https://github.com/van-riper/etymyriad/compare/v0.2.5..v0.3.0
[0.2.5]: https://github.com/van-riper/etymyriad/compare/v0.2.4..v0.2.5
[0.2.4]: https://github.com/van-riper/etymyriad/compare/v0.2.3..v0.2.4
[0.2.3]: https://github.com/van-riper/etymyriad/compare/v0.2.2..v0.2.3
[0.2.2]: https://github.com/van-riper/etymyriad/compare/v0.2.1..v0.2.2
[0.2.1]: https://github.com/van-riper/etymyriad/compare/v0.2.0..v0.2.1
[0.2.0]: https://github.com/van-riper/etymyriad/compare/v0.1.9..v0.2.0
[0.1.9]: https://github.com/van-riper/etymyriad/compare/v0.1.8..v0.1.9
[0.1.8]: https://github.com/van-riper/etymyriad/compare/v0.1.7..v0.1.8
[0.1.7]: https://github.com/van-riper/etymyriad/compare/v0.1.6..v0.1.7
[0.1.6]: https://github.com/van-riper/etymyriad/compare/v0.1.5..v0.1.6
[0.1.5]: https://github.com/van-riper/etymyriad/compare/v0.1.4..v0.1.5
[0.1.4]: https://github.com/van-riper/etymyriad/compare/v0.1.3..v0.1.4
[0.1.3]: https://github.com/van-riper/etymyriad/compare/v0.1.2..v0.1.3
[0.1.2]: https://github.com/van-riper/etymyriad/compare/v0.1.1..v0.1.2
[0.1.1]: https://github.com/van-riper/etymyriad/compare/v0.1.0..v0.1.1
[0.1.0]: https://github.com/van-riper/etymyriad/tree/v0.1.0

<!-- generated by git-cliff -->
