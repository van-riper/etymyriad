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
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lang_code        TEXT NOT NULL REFERENCES language(code),
    headword         TEXT NOT NULL,         -- e.g. 'water', 'aqua', '*wréh₂ds'
    gloss            TEXT,                  -- short sense, disambiguates homographs
    romanization     TEXT,                  -- for non-Latin scripts
    pos              TEXT,                  -- part of speech, when known
    is_reconstructed BOOLEAN NOT NULL DEFAULT FALSE,  -- true for proto-forms
    source_ref       TEXT NOT NULL          -- Wiktionary page / dump provenance
);

-- Natural identity of a lexeme. COALESCE so NULL glosses collapse to one row
-- per (language, headword) while distinct glosses stay separate (homographs).
CREATE UNIQUE INDEX lexeme_natural_key
    ON lexeme (lang_code, headword, COALESCE(gloss, ''));

-- Trigram index for fuzzy / prefix headword search.
CREATE INDEX lexeme_headword_trgm ON lexeme USING gin (headword gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- Etymology (edges)
-- ---------------------------------------------------------------------------

CREATE TABLE etymology (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    src_id      BIGINT NOT NULL REFERENCES lexeme(id) ON DELETE CASCADE, -- ancestor
    dst_id      BIGINT NOT NULL REFERENCES lexeme(id) ON DELETE CASCADE, -- descendant
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
