-- etymyriad: canonical Postgres schema (v1).
--
-- The data model is a directed, provenance-carrying graph:
--   * lexeme   = a word / morpheme in one language (a node)
--   * etymology = a typed, directed, cited relation between two lexemes (an edge)
--
-- Edge direction is ANCESTOR (src) -> DESCENDANT (dst). So:
--   * "backtrace of X"   = walk edges where dst = X, recursively toward src.
--   * "descendants of X" = walk edges where src = X, recursively toward dst.
--
-- Every edge carries a `source_ref` back to its Wiktionary origin. Nothing in
-- this graph is unsourced. Nothing is AI-generated. That is what makes the
-- dataset citable. See DATA_LICENSE.md.

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------

-- Lives in its own schema, never public: see migration 0010's header
-- for why a blue/green reload's schema swap requires this.
CREATE SCHEMA IF NOT EXISTS ext;
CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA ext;

-- ---------------------------------------------------------------------------
-- Languages
-- ---------------------------------------------------------------------------
-- Keyed by Wiktionary language code, which includes proto-languages
-- (e.g. 'ine-pro' = Proto-Indo-European, 'la' = Latin, 'grc' = Ancient Greek).

CREATE TABLE language (
    code        TEXT PRIMARY KEY,        -- e.g. 'en', 'la', 'ine-pro'
    name        TEXT NOT NULL,           -- e.g. 'English', 'Proto-Indo-European'
    lang_family TEXT,                    -- e.g. 'Indo-European'
    is_proto    BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------------------
-- Etymological relation types
-- ---------------------------------------------------------------------------
-- Mirrors the relations Wiktionary actually encodes via its etymology
-- templates ({{inh}}, {{bor}}, {{der}}, {{cog}}, {{af}}, ...).

CREATE TYPE etym_rel_type AS ENUM (
    'inherited',              -- {{inh}}  passed down within a language lineage
    'borrowed',               -- {{bor}}  loanword from another language
    'learned_borrowing',      -- {{lbor}} deliberate scholarly borrowing
    'semi_learned_borrowing', -- {{slbor}}
    'derived',                -- {{der}}  derived from, mechanism unspecified
    'root',                   -- {{root}} ultimate root morpheme
    'affix',                  -- {{af}}/{{prefix}}/{{suffix}} morphology
    'compound',               -- {{com}}  compound of components
    'calque',                 -- {{cal}}  loan translation
    'cognate',                -- {{cog}}  related, not a direct ancestor (undirected-ish)
    'mention',                -- {{m}}    a bare mention in etymology prose
    'onomatopoeic',           -- coined imitatively (no ancestor)
    'surface_analysis'        -- {{surf}} same-language surface decomposition
);

-- ---------------------------------------------------------------------------
-- Lexemes (nodes)
-- ---------------------------------------------------------------------------

CREATE TABLE lexeme (
    -- UUID, not GENERATED ALWAYS AS IDENTITY: the identity column's
    -- backing SQL sequence forces one round trip per row on CockroachDB
    -- (measured 170 rows/s vs 624 rows/s with gen_random_uuid() on the
    -- real cluster), since a sequence needs a coordinated shared counter
    -- while a random UUID needs no coordination at all. gen_random_uuid()
    -- is built into both Postgres 13+ and CockroachDB, so this keeps one
    -- schema working on both engines rather than branching per engine.
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lang_code        TEXT NOT NULL REFERENCES language(code),
    headword         TEXT NOT NULL,         -- e.g. 'etymology', 'aqua', '*wréh₂ds'
    etymology_number TEXT,                  -- Wiktextract's own sense grouping
    romanization     TEXT,                  -- for non-Latin scripts
    is_reconstructed BOOLEAN NOT NULL DEFAULT FALSE,  -- true for proto-forms
    -- true when only known from another entry's etymology template,
    -- with no dictionary entry of its own (a "red link")
    is_redlink       BOOLEAN NOT NULL DEFAULT FALSE,
    source_ref       TEXT NOT NULL,         -- Wiktionary page / dump provenance
    -- Materialized so the natural key below can be a plain-column unique
    -- index: some engines (CockroachDB) can't infer an ON CONFLICT arbiter
    -- from an expression index, only from literal columns.
    etym_key         TEXT GENERATED ALWAYS AS (
                         COALESCE(etymology_number, '')) STORED,
    -- Total in+out etymology edges touching this lexeme, recomputed by
    -- `load.py` after every run's purge step. Not a weighted centrality
    -- measure (eigenvector, betweenness, PageRank): raw degree is a
    -- fine proxy for "how connected is this word" and a plain SQL
    -- aggregate over etymology, not a graph algorithm.
    degree           INTEGER NOT NULL DEFAULT 0
);

-- Natural identity of a lexeme. etym_key collapses a NULL etymology_number
-- to one row per (language, headword); distinct etymology_numbers stay
-- separate (Wiktionary's own signal for genuinely different derivations,
-- e.g. "reverse" the adj/adv/noun vs. the unrelated verb sense).
CREATE UNIQUE INDEX lexeme_natural_key
    ON lexeme (lang_code, headword, etym_key);

-- Trigram index for fuzzy / prefix headword search.
CREATE INDEX lexeme_headword_trgm
    ON lexeme USING gin (headword ext.gin_trgm_ops);

-- Supports randomLexeme's `degree > 0` filter without a full table scan.
CREATE INDEX lexeme_degree_idx ON lexeme (degree) WHERE degree > 0;

-- ---------------------------------------------------------------------------
-- Senses
-- ---------------------------------------------------------------------------
-- One row per originating Wiktextract entry merged into a lexeme. A lexeme
-- now groups by etymology_number, not by gloss/pos, so a single lexeme (e.g.
-- "reverse" adj/adv/noun, one shared derivation) can carry more than one
-- gloss/pos -- those no longer fit as plain columns on lexeme itself.

CREATE TABLE sense (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lexeme_id   UUID NOT NULL REFERENCES lexeme(id) ON DELETE CASCADE,
    pos         TEXT,
    gloss       TEXT,
    source_ref  TEXT NOT NULL,
    pos_key     TEXT GENERATED ALWAYS AS (COALESCE(pos, '')) STORED,
    gloss_key   TEXT GENERATED ALWAYS AS (COALESCE(gloss, '')) STORED
);

CREATE UNIQUE INDEX sense_natural_key
    ON sense (lexeme_id, pos_key, gloss_key);

-- ---------------------------------------------------------------------------
-- Etymology (edges)
-- ---------------------------------------------------------------------------

CREATE TABLE etymology (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    src_id      UUID NOT NULL REFERENCES lexeme(id) ON DELETE CASCADE, -- ancestor
    dst_id      UUID NOT NULL REFERENCES lexeme(id) ON DELETE CASCADE, -- descendant
    rel_type    etym_rel_type NOT NULL,
    source_ref  TEXT NOT NULL,            -- Wiktionary page / template provenance
    -- 1-based morpheme position within an affix/root/compound template
    -- (e.g. 1 for a prefix, 2 for the root it attaches to), or NULL for
    -- a rel_type that never decomposes a word into ordered pieces.
    piece_order SMALLINT,
    CONSTRAINT etymology_no_self_loop CHECK (src_id <> dst_id),
    CONSTRAINT etymology_unique_edge UNIQUE (src_id, dst_id, rel_type)
);

-- Traversal index for ancestors/backtrace (by dst). No separate src_id
-- index: etymology_unique_edge above already leads with src_id, so it
-- serves descendant lookups (by src) too.
CREATE INDEX etymology_dst_idx ON etymology (dst_id);

-- ---------------------------------------------------------------------------
-- Reference queries
-- ---------------------------------------------------------------------------
-- Linear backtrace: all ancestors of lexeme :id up to :max_depth.
-- Implemented by /tree's ancestor walk (web/src/lib/server/queries.ts),
-- which additionally caps fan-out per parent at each hop:
--
--   WITH RECURSIVE ancestors AS (
--       SELECT e.src_id, e.dst_id, e.rel_type, 1 AS depth
--       FROM etymology e WHERE e.dst_id = :id
--     UNION ALL
--       SELECT e.src_id, e.dst_id, e.rel_type, a.depth + 1
--       FROM etymology e JOIN ancestors a ON e.dst_id = a.src_id
--       WHERE a.depth < :max_depth
--   )
--   SELECT * FROM ancestors;
