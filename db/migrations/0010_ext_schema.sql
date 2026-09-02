-- Migration 0010: move pg_trgm into its own `ext` schema.
--
-- A blue/green reload renames `public` to a rollback schema and
-- promotes a freshly-built `loading` schema in its place every run.
-- An extension anchored in `public` would ping-pong
-- between schemas on every swap and eventually get dropped along
-- with an old generation's schema, taking `gin_trgm_ops` -- and the
-- `lexeme_headword_trgm` index it backs -- with it. `ext` is never
-- renamed or dropped, so the extension survives every swap;
-- `db/schema.sql`'s index DDL references it as `ext.gin_trgm_ops` so
-- it resolves regardless of which schema is being built.
--
-- Deploy this ahead of the first blue/green run, on both local dev
-- and Neon.
--
-- Drop and recreate rather than `ALTER EXTENSION ... SET SCHEMA`:
-- on Neon, pg_trgm's underlying functions stay owned by the
-- internal `cloud_admin` role even though `neondb_owner` owns the
-- extension object itself, and SET SCHEMA requires ownership of
-- every object the extension comprises. CASCADE takes the trigram
-- index with it, so rebuild that too.

CREATE SCHEMA IF NOT EXISTS ext;
DROP EXTENSION IF EXISTS pg_trgm CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA ext;

CREATE INDEX IF NOT EXISTS lexeme_headword_trgm
    ON lexeme USING gin (headword ext.gin_trgm_ops);
