-- Migration 0009: replace lexeme_layout with lexeme.degree.
--
-- `lexeme_layout`'s only surviving reader, randomLexeme, only ever
-- read its `degree` column (an `(x, y)` nobody renders since `/graph`
-- was retired). Moves `degree` onto `lexeme` directly and drops the
-- DrL layout table, its 8.4M-row `executemany` upsert, and the
-- `igraph` dependency that computed it -- roughly 2/3 of every
-- reload's wall clock for a value a plain aggregate computes in
-- seconds.
--
-- Backfills in the same deploy, not a bare `DEFAULT 0`: a bare
-- default against an already-populated table (Neon always qualifies)
-- would leave every existing lexeme's degree wrong until the next
-- full reload, the same trap as 0007_lexeme_is_redlink.sql.

ALTER TABLE lexeme ADD COLUMN degree INTEGER NOT NULL DEFAULT 0;

WITH degree_counts AS (
    SELECT lexeme_id, sum(edge_count) AS degree
    FROM (
        SELECT src_id AS lexeme_id, count(*) AS edge_count
        FROM etymology GROUP BY src_id
        UNION ALL
        SELECT dst_id AS lexeme_id, count(*) AS edge_count
        FROM etymology GROUP BY dst_id
    ) AS endpoint_counts
    GROUP BY lexeme_id
)
UPDATE lexeme SET degree = degree_counts.degree
FROM degree_counts
WHERE lexeme.id = degree_counts.lexeme_id;

CREATE INDEX lexeme_degree_idx ON lexeme (degree) WHERE degree > 0;

DROP TABLE lexeme_layout;
