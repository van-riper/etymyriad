-- Migration 0003: per-lexeme degree/importance ranking.
--
-- Adds `degree` to `lexeme_layout`, the same batch job's importance
-- signal for a low-zoom/overview render: total in+out etymology edges
-- touching the lexeme, chosen over a weighted centrality measure since
-- it falls out of the edge list the layout pass already loads. See
-- ETYM-68.

ALTER TABLE lexeme_layout ADD COLUMN degree INTEGER NOT NULL DEFAULT 0;

CREATE INDEX lexeme_layout_degree_idx ON lexeme_layout (degree DESC);
