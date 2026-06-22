# Data integrity & provenance rules

The project's correctness contract. These are **invariants, not preferences**:
the dataset's entire value is that it is sourced and citable, so violating any
of these undermines the product. Marker: **(P)** = project-specific (all of
these are).

## Provenance: nothing is unsourced

- Every `lexeme` and every `etymology` edge carries a non-empty `source_ref`
  that traces back to its origin in the source data.
- `source_ref` must be stable and resolvable back to the source (a Wiktionary
  page / kaikki entry, ideally with the dump version). Keep the format
  consistent across the pipeline.
- A row with no traceable source does not enter the graph. Drop it instead.

## No invented facts

- **Never generate etymological facts** with an LLM, a heuristic, or a guess.
  Nodes and edges come only from parsed source data.
- AI (deferred) may later *summarize* or *search over* the graph. It must never
  *author* a node or edge.
- When the parser is uncertain, **drop or flag** the item. Do not coerce it into
  a plausible-looking relation.

## Direction, types, and reconstruction

- Edge direction is **ancestor (`src`) -> descendant (`dst`)**. Preserve it:
  backtrace walks `dst -> src`, descendants walk `src -> dst`.
- Map source templates to a `RelType` only through the validated `TEMPLATE_RELS`
  table. An unknown template is logged and skipped, never guessed into an
  existing type.
- Reconstructed forms (proto-languages, leading `*`) must set
  `is_reconstructed = true`.

## Idempotency

- Loads are idempotent: re-running the pipeline on the same input yields the
  same rows. Lexemes upsert on their natural key, and edges are unique on
  `(src_id, dst_id, rel_type)`. No duplicate-driven drift across runs.

## Identity & homographs

- A lexeme's natural key is `(lang_code, headword, COALESCE(gloss, ''))`.
- Do not merge distinct senses by discarding their glosses, and do not split a
  single sense by inventing glosses.

## Validation before trust

- Cross-check parser output against the **Etymological Wordnet** before trusting
  a data release, and spot-check golden etymologies (e.g. *water* -> PIE
  *\*wódr̥*). Treat any divergence as a parser bug until explained.

## Serving (anti-noise)

- Never return or render the whole graph. Every response is a depth-bounded
  ego-network or a single linear backtrace.

## Licensing

- The derived dataset is **CC BY-SA 4.0** (inherited from Wiktionary). Any data
  export must attribute Wiktionary and carry the license. See the
  [Licensing section of the README](../../README.md#licensing).
