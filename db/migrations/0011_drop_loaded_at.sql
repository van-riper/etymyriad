-- Migration 0011: drop the loaded_at run marker.
--
-- 0008_loaded_at.sql added loaded_at to prune rows a reload no
-- longer produces. The blue/green reload builds a fresh `loading`
-- schema and swaps it in wholesale, so a stale row simply never
-- makes it into the new generation -- there is nothing left for
-- loaded_at to prune. `db/schema.sql` already dropped these columns
-- directly; this migration brings the migration chain itself back
-- in sync, so replaying migrations from scratch produces the same
-- schema as applying `schema.sql` fresh.

DROP INDEX lexeme_loaded_at_idx;
ALTER TABLE lexeme DROP COLUMN loaded_at;

DROP INDEX sense_loaded_at_idx;
ALTER TABLE sense DROP COLUMN loaded_at;

DROP INDEX etymology_loaded_at_idx;
ALTER TABLE etymology DROP COLUMN loaded_at;
