-- Migration 0005: per-lexeme cluster assignment.
--
-- Adds `cluster_id` to `lexeme_layout`, computed offline via igraph's
-- Leiden community-detection algorithm (etymyriad.layout.
-- compute_clusters), the same batch job that already computes
-- x/y/degree. Powers a clustered, legible whole-graph overview
-- instead of literally every lexeme -- see ETYM-108's follow-up
-- design doc and queries.ts's overviewGraph().
--
-- DEFAULT 0 backfills existing rows so the column can be NOT NULL
-- immediately; DROP DEFAULT afterward so every future row must carry
-- a real, deliberately-computed value -- matching x/y's own
-- no-default NOT NULL definition, not degree's permanent DEFAULT 0
-- (0 is a meaningful "no edges" value for degree; it is not a
-- meaningful cluster assignment).

ALTER TABLE lexeme_layout ADD COLUMN cluster_id INTEGER NOT NULL DEFAULT 0;
ALTER TABLE lexeme_layout ALTER COLUMN cluster_id DROP DEFAULT;

CREATE INDEX lexeme_layout_cluster_id_idx ON lexeme_layout (cluster_id);
