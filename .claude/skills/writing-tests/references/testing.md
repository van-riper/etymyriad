# Testing rules

Operative, self-contained ruleset for tests across the pipeline (`pipeline/`)
and web (`web/`). Markers: **(H)** = house preference, **(P)** =
project-specific.

## General (both stacks)

- Test the **behavior/contract**, not the implementation. Assert on observable
  outputs, not private helpers or internal call order.
- **Arrange-act-assert:** one clear setup, one action, one focused set of
  checks. One logical assertion focus per test **(H)**.
- **Deterministic always:** no real clock, network, filesystem-of-record, or
  unseeded randomness. Inject a fixed clock/seed and freeze inputs **(H)**.
- Prefer **fixtures over heavy mocks.** Mock only true boundaries (network, DB),
  not the unit under test.
- A test that is flaky or order-dependent is a bug. Each test stands alone and
  cleans up after itself.

## Pipeline: Python (pytest)

- Run with **`uv run pytest`**, coverage via **pytest-cov**
  (`uv run pytest --cov`). Tests live under `pipeline/tests/`.
- **Fixture-based unit tests** for `parse`, `normalize`, and `load`: feed each a
  small in-memory Wiktextract record and assert on the `Lexeme`/`EtymEdge`
  output. Keep sample records as pytest fixtures or `tests/data/` files **(P)**.
- **Golden tests on known etymologies (P):** lock correctness against a curated
  set, e.g. `water` -> Proto-Indo-European `*wódr̥`. A golden test asserts the
  full expected node + edge (lang, headword, `rel_type`, direction,
  `is_reconstructed`, `source_ref`). These guard against silent data drift.
- **No network or DB in unit tests (P):** never hit kaikki.org or Postgres. Use
  fixtures for input and an in-memory/transaction-rolled-back stand-in for
  `load`. Any DB-touching test is integration-tier and opt-in, not default.
- Naming: **`test_<unit>_<behavior>`**, e.g.
  `test_normalize_drops_unknown_template`,
  `test_load_upserts_lexeme_on_natural_key`. One file per module under test.
- Cover the invariant edges deliberately: edge **direction** (`src -> dst`),
  unknown-template skip, reconstruction flag, and natural-key idempotency
  (re-loading the same input yields the same rows).

## Web: SvelteKit / TypeScript

- **`svelte-check` must stay clean** (`npm run check`). A type error is a test
  failure. CI gates on it.
- Unit tests with **vitest** for:
  - `lib/server/queries.ts`, the row-to-graph **shaping** logic (depth bounds,
    ego-network assembly, backtrace ordering). Feed canned query rows and assert
    the shaped result.
  - `lib/types`, any guards/transforms that enforce the shared graph types.
- **Endpoint test** for `/api/word/[lang]/[headword]`: exercise the
  `+server.ts` handler with a stubbed DB client and assert status, shape, and
  that the response is a depth-bounded slice (never the whole graph).
- A **Playwright smoke test** (search -> graph renders) comes later. Stub it in,
  but it is not a v1 gate.

## Tie-in: data integrity is enforced here (P)

- The golden and validation tests are **how the data-integrity invariants reach
  CI.** They are the executable form of `.claude/rules/data-integrity.md`:
  provenance (every node/edge has a `source_ref`), no-invented-facts (output
  comes only from the fixture input), and correct edges (direction, type,
  reconstruction).
- Spot-checked golden etymologies double as the parser's cross-check against the
  Etymological Wordnet. Treat any golden-test divergence as a parser bug until
  explained, never by editing the golden value to match buggy output.
