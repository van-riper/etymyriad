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

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram search on headwords

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
    'onomatopoeic'            -- coined imitatively (no ancestor)
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
    source_ref       TEXT NOT NULL,         -- Wiktionary page / dump provenance
    -- Materialized so the natural key below can be a plain-column unique
    -- index: some engines (CockroachDB) can't infer an ON CONFLICT arbiter
    -- from an expression index, only from literal columns.
    etym_key         TEXT GENERATED ALWAYS AS (
                         COALESCE(etymology_number, '')) STORED
);

-- Natural identity of a lexeme. etym_key collapses a NULL etymology_number
-- to one row per (language, headword); distinct etymology_numbers stay
-- separate (Wiktionary's own signal for genuinely different derivations,
-- e.g. "reverse" the adj/adv/noun vs. the unrelated verb sense).
CREATE UNIQUE INDEX lexeme_natural_key
    ON lexeme (lang_code, headword, etym_key);

-- Trigram index for fuzzy / prefix headword search.
CREATE INDEX lexeme_headword_trgm ON lexeme USING gin (headword gin_trgm_ops);

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
    CONSTRAINT etymology_no_self_loop CHECK (src_id <> dst_id),
    CONSTRAINT etymology_unique_edge UNIQUE (src_id, dst_id, rel_type)
);

-- Traversal index for ancestors/backtrace (by dst). No separate src_id
-- index: etymology_unique_edge above already leads with src_id, so it
-- serves descendant lookups (by src) too.
CREATE INDEX etymology_dst_idx ON etymology (dst_id);

-- ---------------------------------------------------------------------------
-- Layout (precomputed node positions and importance ranking)
-- ---------------------------------------------------------------------------
-- One row per lexeme, computed once offline over the full graph by the
-- `etymyriad layout` batch job (see ETYM-67). Every ego-network fetch
-- reads these coordinates rather than recomputing a layout per request.
--
-- `degree` is the same job's importance signal for a low-zoom/overview
-- render (see ETYM-68): total in+out etymology edges touching the
-- lexeme. Chosen over a weighted centrality measure (eigenvector,
-- betweenness, PageRank) because it falls out of the edge list the
-- layout pass already loads -- no extra graph algorithm or query -- and
-- is a fine proxy for "how connected is this word" for that use case.

CREATE TABLE lexeme_layout (
    lexeme_id    UUID PRIMARY KEY REFERENCES lexeme(id) ON DELETE CASCADE,
    x            DOUBLE PRECISION NOT NULL,
    y            DOUBLE PRECISION NOT NULL,
    degree       INTEGER NOT NULL DEFAULT 0,
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Indexable projection of (x, y): a GiST index over a native
    -- point/box type needs a point-typed column. GENERATED keeps it in
    -- sync with x/y automatically, so layout.py never writes it
    -- directly. See ETYM-69.
    pos          POINT GENERATED ALWAYS AS (point(x, y)) STORED
);

-- Supports "top N by importance" without a full table scan.
CREATE INDEX lexeme_layout_degree_idx ON lexeme_layout (degree DESC);

-- Supports viewport queries: `WHERE pos <@ box(point(minX,minY),
-- point(maxX,maxY))`, using Postgres's built-in point_ops GiST
-- opclass (no PostGIS). See ETYM-69.
CREATE INDEX lexeme_layout_pos_idx ON lexeme_layout USING gist (pos);

-- ---------------------------------------------------------------------------
-- Reference queries (the API will parameterize these)
-- ---------------------------------------------------------------------------
--
-- Linear backtrace: all ancestors of lexeme :id up to :max_depth:
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
--
-- Ego-network: neighborhood of :id within :max_depth in BOTH directions
-- (this is the anti-noise primitive: never load the whole graph, only a slice):
--
--   WITH RECURSIVE ego AS (
--       SELECT :id AS lexeme_id, 0 AS depth
--     UNION
--       SELECT CASE WHEN e.src_id = g.lexeme_id THEN e.dst_id ELSE e.src_id END,
--              g.depth + 1
--       FROM ego g
--       JOIN etymology e ON g.lexeme_id IN (e.src_id, e.dst_id)
--       WHERE g.depth < :max_depth
--   )
--   SELECT DISTINCT lexeme_id FROM ego;
