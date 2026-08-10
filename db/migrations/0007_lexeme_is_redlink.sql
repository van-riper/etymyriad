-- Migration 0007: redlink flag on lexeme.
--
-- Adds `is_redlink`, true when a lexeme is known only from another
-- entry's etymology template and has no dictionary entry of its own
-- (a "red link"). Wiktextract carries no direct signal for this; the
-- loader's upsert defaults a referenced-only lexeme to true and
-- AND-latches it false once the lexeme's own entry loads.

ALTER TABLE lexeme ADD COLUMN is_redlink BOOLEAN NOT NULL DEFAULT FALSE;
