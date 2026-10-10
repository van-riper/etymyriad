"""Schema names, DDL, and the reload pipeline's guard checks."""

from __future__ import annotations

import zlib

import psycopg
import psycopg.sql

_TARGET_SCHEMA = "loading"
_LIVE_SCHEMA = "public"

_LOAD_LOCK_KEY = zlib.crc32(b"etymyriad.load_edges")

_STAGING_DDL_SQL = """
    CREATE UNLOGGED TABLE stg_term (
        lang_code TEXT NOT NULL,
        headword TEXT NOT NULL,
        section SMALLINT NOT NULL,
        is_reconstructed BOOLEAN NOT NULL,
        part_of_speech TEXT,
        gloss TEXT,
        has_sense BOOLEAN NOT NULL
    );

    CREATE UNLOGGED TABLE stg_edge (
        src_lang_code TEXT NOT NULL,
        src_headword TEXT NOT NULL,
        src_section SMALLINT NOT NULL,
        src_variety_code TEXT,
        dst_lang_code TEXT NOT NULL,
        dst_headword TEXT NOT NULL,
        dst_section SMALLINT NOT NULL,
        rel_type TEXT NOT NULL,
        anchor TEXT NOT NULL,
        piece_order SMALLINT
    );
"""

_DROP_DEFERRED_INDEXES_SQL = """
    ALTER TABLE term DROP CONSTRAINT term_natural_key;
    DROP INDEX sense_term_idx;
    ALTER TABLE edge DROP CONSTRAINT edge_pkey;
    DROP INDEX edge_dst_idx;
    DROP INDEX pickable_term_language_idx;
"""


def _set_search_path_or_raise(cursor: psycopg.Cursor, schema: str) -> None:
    """Set search_path and confirm it actually took effect.

    A pooled connection (e.g. a transaction-pooling proxy) can route a
    bare SET outside a transaction to a different backend than the
    statements that follow it, the one way this pipeline could silently
    write into public instead of a scratch schema.

    Args:
        cursor: Database cursor with an active connection.
        schema: The schema search_path must resolve to.

    Raises:
        RuntimeError: If search_path didn't take effect as expected.
    """
    cursor.execute(
        psycopg.sql.SQL("SET search_path TO {}").format(
            psycopg.sql.Identifier(schema)
        )
    )
    cursor.execute("SELECT current_schema()")
    row = cursor.fetchone()
    if row is None or row[0] != schema:
        msg = (
            f"search_path did not take effect: expected {schema!r}, got {row!r}"
        )
        raise RuntimeError(msg)


def _acquire_load_lock_or_raise(cursor: psycopg.Cursor) -> None:
    """Take the reload's advisory lock, or fail fast if one's in flight.

    Two concurrent reloads would otherwise race on the same `loading`
    schema, with the second run's drop stomping the first run's
    in-progress rebuild. The lock is session-level: it releases when
    `cursor`'s connection closes.

    Args:
        cursor: Database cursor with an active connection.

    Raises:
        RuntimeError: If another connection already holds the lock.
    """
    cursor.execute("SELECT pg_try_advisory_lock(%s)", (_LOAD_LOCK_KEY,))
    row = cursor.fetchone()
    if row is None or not row[0]:
        msg = "another load_edges run is already in progress"
        raise RuntimeError(msg)


def _rebuild_schema(cursor: psycopg.Cursor, schema_sql: str) -> None:
    """Drop and recreate loading from schema.sql and defer its indexes.

    The five bulk-load-hostile indexes/constraint go immediately after,
    so COPY and the merge inserts that follow hit no index maintenance
    at all. `schema_sql`'s own index DDL builds them once here only to
    drop them again; a later bulk-rebuild step recreates them once the
    merge lands.

    Args:
        cursor: Database cursor with an active connection.
        schema_sql: The DDL text from db/schema.sql to execute.
    """
    cursor.execute(f"DROP SCHEMA IF EXISTS {_TARGET_SCHEMA} CASCADE")
    cursor.execute(f"CREATE SCHEMA {_TARGET_SCHEMA}")
    _set_search_path_or_raise(cursor, _TARGET_SCHEMA)
    cursor.execute(psycopg.sql.SQL(schema_sql))  # ty: ignore[invalid-argument-type]
    cursor.execute(_STAGING_DDL_SQL)
    cursor.execute(_DROP_DEFERRED_INDEXES_SQL)
