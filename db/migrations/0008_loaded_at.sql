-- Migration 0008: loaded_at run marker on lexeme/etymology/sense.
--
-- Stamped with the loading run's start time on every upsert. A full
-- `load`/`all` run purges any row older than its own stamp once it
-- finishes, so a headword or edge the source dump no longer produces
-- doesn't linger forever. A bare `DEFAULT now()` is safe against the
-- 0007 AND-latch incident's failure mode: loaded_at has no latch
-- semantics, so every subsequent upsert overwrites it unconditionally
-- regardless of what the migration backfills existing rows to.

ALTER TABLE lexeme ADD COLUMN loaded_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX lexeme_loaded_at_idx ON lexeme (loaded_at);

ALTER TABLE sense ADD COLUMN loaded_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX sense_loaded_at_idx ON sense (loaded_at);

ALTER TABLE etymology ADD COLUMN loaded_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX etymology_loaded_at_idx ON etymology (loaded_at);
