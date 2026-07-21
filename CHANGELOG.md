# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
