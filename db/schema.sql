-- etymyriad: canonical Postgres schema.
--
-- A directed, provenance-carrying graph:
--   * term = one headword in one language (a node): a Wiktionary page's
--     language section, or a redlink known only from another page's
--     templates. A redlink is a term with no sense rows.
--   * edge = a typed relation, src -> dst meaning ancestor -> descendant.
--
-- Backtrace walks dst -> src; descendants walk src -> dst.
--
-- A section is Wiktionary's "Etymology N" number, stored on an edge end
-- or a sense only where the source states it. 0 means unspecified.
--
-- Every edge carries an anchor into the dst page that states it, and
-- source_ref() derives the full citation from the dataset's dump date.
-- Nothing here is unsourced, and nothing is AI-generated.

CREATE TYPE language_kind AS ENUM (
    'regular',
    'reconstructed',
    'appendix-constructed',
    'collective'
);

CREATE TABLE language (
    id   SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,  -- Wiktionary code: 'en', 'gem-pro', 'gem'
    name TEXT NOT NULL,
    kind language_kind NOT NULL
);

-- Etymology-only lects such as 'la-lat'. Wiktionary files their terms
-- under the full language, so a variety only ever labels an edge's src.
CREATE TABLE variety (
    id          SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    language_id SMALLINT NOT NULL REFERENCES language (id),
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL
);

CREATE INDEX variety_language_idx ON variety (language_id);

CREATE TABLE dataset (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    dump_date DATE NOT NULL
);

CREATE TABLE term (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    language_id      SMALLINT NOT NULL REFERENCES language (id),
    headword         TEXT NOT NULL,
    is_reconstructed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT term_natural_key UNIQUE (language_id, headword)
);

CREATE TABLE sense (
    term_id        INTEGER NOT NULL REFERENCES term (id),
    section        SMALLINT NOT NULL DEFAULT 0,
    part_of_speech TEXT,
    gloss          TEXT
);

CREATE INDEX sense_term_idx ON sense (term_id);

-- Mirrors the relations Wiktionary encodes in its etymology templates.
CREATE TYPE edge_type AS ENUM (
    'inherited',              -- {{inh}}
    'borrowed',               -- {{bor}}
    'learned_borrowing',      -- {{lbor}}
    'semi_learned_borrowing', -- {{slbor}}
    'derived',                -- {{der}}
    'root',                   -- {{root}}
    'affix',                  -- {{af}}, {{prefix}}, {{suffix}}
    'compound',               -- {{com}}
    'calque',                 -- {{cal}}
    'mention',                -- {{m}}, excluded from tree walks
    'surface_analysis',       -- {{surf}}
    'inflection'              -- lemma -> a cited inflected form
);

CREATE TABLE edge (
    src_term_id    INTEGER   NOT NULL REFERENCES term (id),
    src_section    SMALLINT  NOT NULL DEFAULT 0,
    dst_term_id    INTEGER   NOT NULL REFERENCES term (id),
    dst_section    SMALLINT  NOT NULL DEFAULT 0,
    rel_type       edge_type NOT NULL,
    src_variety_id SMALLINT  REFERENCES variety (id),
    anchor         TEXT      NOT NULL,  -- e.g. 'etymology_templates:0:af'
    piece_order    SMALLINT,            -- 1-based morpheme position
    CONSTRAINT edge_pkey PRIMARY KEY
        (src_term_id, dst_term_id, dst_section, rel_type, src_section),
    -- Tree nodes are terms, so a same-term edge would make a node its
    -- own parent.
    CONSTRAINT edge_no_self_loop CHECK (src_term_id <> dst_term_id)
);

CREATE INDEX edge_dst_idx ON edge (dst_term_id, dst_section);

-- Terms the random-word button may land on: a real entry with at least
-- one non-mention edge. Built once per load, after the edges.
CREATE TABLE pickable_term (
    term_id     INTEGER PRIMARY KEY REFERENCES term (id),
    language_id SMALLINT NOT NULL REFERENCES language (id)
);

CREATE INDEX pickable_term_language_idx
    ON pickable_term (language_id, term_id);

-- The one place the citation format lives. to_char, not a cast, so the
-- session's DateStyle can't change it. An anchor's template index counts
-- within one section, so a nonzero section is part of the citation.
CREATE FUNCTION source_ref(
    lang_code TEXT, headword TEXT, anchor TEXT DEFAULT NULL,
    section INTEGER DEFAULT 0
) RETURNS TEXT
LANGUAGE sql STABLE
AS $$
    SELECT 'wiktionary:' || to_char(dump_date, 'YYYY-MM-DD') || ':'
           || lang_code || ':' || headword
           || CASE WHEN section > 0 THEN ':' || section ELSE '' END
           || COALESCE('#' || anchor, '')
    FROM dataset
$$;
