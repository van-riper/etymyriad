# SQL & schema rules (db/)

Operative, self-contained ruleset for SQL and schema changes. There is no single
external baseline. This follows common PostgreSQL conventions and the style
already established in `db/schema.sql`. Markers: **(H)** = house preference,
**(P)** = project-specific.

Postgres is the system of record, and `db/schema.sql` is its canonical
definition.

## Formatting

- **UPPERCASE** SQL keywords (`CREATE TABLE`, `PRIMARY KEY`, `REFERENCES`) and
  **snake_case** identifiers. Match `db/schema.sql`.
- One column or constraint per line. Group related statements and separate
  sections with `-- ----` divider comments, as the schema already does.
- Explicit column lists in application `INSERT`/`SELECT`, never `SELECT *` in
  app queries.

## Naming

- **Tables are singular**: `lexeme`, `etymology`, `language`.
- Columns are snake_case, and the `_id` suffix marks a primary or foreign key
  (`src_id`, `dst_id`). Append a unit when one applies, per the house naming
  rule.
- Enum types are `<noun>_type` (e.g. `etym_rel_type`), and enum values are
  `lower_snake`.
- **Name every constraint explicitly**, as `<table>_<purpose>`:
  `etymology_unique_edge`, `etymology_no_self_loop`.
- Indexes are `<table>_<columns>_idx` (`etymology_src_idx`) or
  `<table>_<purpose>` for expression/partial indexes (`lexeme_natural_key`,
  `lexeme_headword_trgm`).

## Query safety & correctness

- **Always parameterize.** Never assemble SQL by string-concatenating or
  interpolating request data. Python uses psycopg parameters (`%s`). The web app
  uses the Neon tagged-template, which parameterizes interpolations. No
  f-strings or template literals carrying raw values into SQL.
- **Bound every traversal.** Recursive CTEs and neighborhood queries must take a
  max-depth (or row-count) limit and clamp it server-side. This enforces both
  the anti-noise principle and the runaway-loop guard.
- Index any column used as a traversal entry point or frequent filter.
- Foreign keys declare explicit `ON DELETE` behavior.

## Migrations

- `db/schema.sql` is the **canonical full snapshot** and what `make db-init`
  applies to a fresh database.
- Incremental changes go in `db/migrations/NNNN_<description>.sql`, zero-padded
  and ordered. Migrations are **append-only**: never edit one that has been
  applied anywhere. Add a new migration instead.
- Migrations are forward-only DDL. Use `IF NOT EXISTS` / `IF EXISTS` where it
  keeps re-application safe.
- A schema change is one atomic commit that updates `db/schema.sql`, adds the
  migration, and updates the code mirrors (see below).

## The three-way mirror (P): the most important schema rule

These three definitions describe the same graph and must never drift:

```text
db/schema.sql  <->  pipeline/src/etymyriad/model.py  <->  web/src/lib/types.ts
   (truth)              (Python graph model)                (TS shared types)
```

Any change to one requires updating all three **in the same commit**. The
`etym_rel_type` enum values in particular must be identical across all three.
