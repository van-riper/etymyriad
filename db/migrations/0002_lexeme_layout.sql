-- Migration 0002: durable global graph layout.
--
-- Adds `lexeme_layout`, storing a precomputed (x, y) position per
-- lexeme, computed once offline over the full graph. See
-- `db/schema.sql` for its current status.

CREATE TABLE lexeme_layout (
    lexeme_id    UUID PRIMARY KEY REFERENCES lexeme(id) ON DELETE CASCADE,
    x            DOUBLE PRECISION NOT NULL,
    y            DOUBLE PRECISION NOT NULL,
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
