-- Migration 0004: spatial index for viewport queries.
--
-- Adds a generated `pos` point column (kept in sync with x/y
-- automatically) and a GiST index over it, so a viewport query can use
-- Postgres's native point_ops opclass (`pos <@ box(...)`) instead of a
-- sequential scan, regardless of total graph size.

ALTER TABLE lexeme_layout
    ADD COLUMN pos POINT GENERATED ALWAYS AS (point(x, y)) STORED;

CREATE INDEX lexeme_layout_pos_idx ON lexeme_layout USING gist (pos);
