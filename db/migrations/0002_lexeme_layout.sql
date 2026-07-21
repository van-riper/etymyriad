-- Migration 0002: durable global graph layout.
--
-- Adds `lexeme_layout`, storing a precomputed (x, y) position per
-- lexeme so every ego-network fetch touching a node returns the same
-- coordinates for it, instead of the client recomputing a layout
-- relative to whatever word it's centered on. See ETYM-67.

CREATE TABLE lexeme_layout (
    lexeme_id    UUID PRIMARY KEY REFERENCES lexeme(id) ON DELETE CASCADE,
    x            DOUBLE PRECISION NOT NULL,
    y            DOUBLE PRECISION NOT NULL,
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
