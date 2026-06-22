---
name: sql-schema-style
description: Use when writing SQL, changing db/schema.sql, adding a db migration, or writing a Postgres query in pipeline/ or web/.
---

# SQL & schema style (db/)

## Overview

Postgres is the system of record and `db/schema.sql` is its canonical
definition. Follow the conventions already established in that file. Precedence:
project CLAUDE.md wins over this skill.

## When to use

- Editing `db/schema.sql`.
- Writing a `CREATE TABLE`, `CREATE INDEX`, or any DDL.
- Adding a migration under `db/migrations/`.
- Writing a recursive-CTE traversal, neighborhood query, or any app query in
  `pipeline/` or `web/`.

## Quick reference

| Rule | Detail |
| ---- | ------ |
| Keywords / identifiers | UPPERCASE keywords, snake_case identifiers. One column or constraint per line. Section dividers `-- ----`. |
| App queries | Explicit column lists. Never `SELECT *` in app queries. |
| Tables | Singular: `lexeme`, `etymology`, `language`. |
| Keys | `_id` suffix marks a primary or foreign key (`src_id`, `dst_id`). Append a unit when one applies. |
| Enums | Type `<noun>_type` (`etym_rel_type`), values `lower_snake`. |
| Constraints | Name EVERY constraint `<table>_<purpose>` (`etymology_unique_edge`, `etymology_no_self_loop`). |
| Indexes | `<table>_<columns>_idx` (`etymology_src_idx`), or `<table>_<purpose>` for expression/partial (`lexeme_natural_key`, `lexeme_headword_trgm`). |
| Parameterize | ALWAYS. psycopg `%s` in Python, Neon tagged-template in web. Never string-concat or interpolate request data into SQL. |
| Bound traversals | Recursive CTEs and neighborhood queries take a max-depth (or row-count) limit, clamped server-side (anti-noise plus runaway-loop guard). |
| Index traversals | Index any column used as a traversal entry point or frequent filter. |
| Foreign keys | Declare explicit `ON DELETE` behavior. |

## Migrations

- `db/schema.sql` is the canonical full snapshot, applied by `make db-init`.
- Incremental changes go in `db/migrations/NNNN_<description>.sql`, zero-padded
  and ordered.
- Append-only and forward-only: never edit an applied migration, add a new one.
  Use `IF NOT EXISTS` / `IF EXISTS` to keep DDL re-runnable.
- A schema change is ONE atomic commit: update `db/schema.sql`, add the
  migration, update the code mirrors.

## Three-way mirror (most important)

These three describe the same graph and must never drift:

```text
db/schema.sql  <->  pipeline/src/etymyriad/model.py  <->  web/src/lib/types.ts
```

Any change to one updates all three in the SAME commit. The `etym_rel_type` enum
values in particular must be identical across all three.

## Full rules

Read `references/sql-style.md` before a schema or migration change.
