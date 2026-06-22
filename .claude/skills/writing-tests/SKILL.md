---
name: writing-tests
description: Use when writing or changing tests in pipeline/ (pytest) or web/ (vitest, svelte-check), including golden etymology tests.
---

# Testing

## Overview

Test the behavior/contract, not the implementation, with arrange-act-assert and
one logical assertion focus per test. Be deterministic always (no real clock,
network, filesystem-of-record, or unseeded randomness) and prefer fixtures over
heavy mocks. This spans the pipeline (Python/pytest) and web (vitest plus
svelte-check).

## When to use

- Adding or changing a `parse`, `normalize`, or `load` test.
- Adding or changing a query-shaping test (`lib/server/queries.ts`).
- Adding or changing an endpoint test for `/api/word/[lang]/[headword]`.
- Writing a golden etymology test that locks a known node and edge.

## Quick reference

Pipeline (Python/pytest):

- Run `uv run pytest`, coverage via pytest-cov (`uv run pytest --cov`). Tests
  live under `pipeline/tests/`.
- Fixture-based unit tests for `parse`, `normalize`, `load`: feed a small
  in-memory Wiktextract record, assert on `Lexeme`/`EtymEdge` output.
- Golden tests on known etymologies (e.g. `water` -> PIE `*wódr̥`) assert the
  full node + edge: lang, headword, `rel_type`, direction, `is_reconstructed`,
  `source_ref`.
- No network or DB in unit tests.
- Naming `test_<unit>_<behavior>`, one file per module under test.
- Deliberately cover edge direction (`src -> dst`), unknown-template skip,
  reconstruction flag, and natural-key idempotency.

Web (TS/Svelte):

- `svelte-check` must stay clean (`npm run check`). A type error is a test
  failure.
- vitest for `queries.ts` row-to-graph shaping (depth bounds, ego-network
  assembly, backtrace ordering) and `lib/types` guards/transforms.
- Endpoint test for `/api/word/[lang]/[headword]` with a stubbed DB: assert
  status, shape, and a depth-bounded slice (never the whole graph).
- Playwright smoke test deferred (not a v1 gate).

## Data-integrity tie-in

Golden and validation tests are how the data-integrity invariants reach CI:
provenance (every node/edge has a `source_ref`), no-invented-facts (output comes
only from the fixture input), and correct edges (direction, type,
reconstruction). A golden-test divergence is a parser bug. Never fix it by
editing the golden value to match buggy output.

## Full rules

Read references/testing.md for the complete rules.
