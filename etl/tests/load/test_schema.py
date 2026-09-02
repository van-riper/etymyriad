"""Tests for schema DDL, migration guard, and search_path plumbing."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from etymyriad.load import load_edges
from etymyriad.load._schema import _rebuild_schema, _set_search_path_or_raise
from etymyriad.model import EtymEdge, Lexeme, RelType, Sense


def test_schema_moves_pg_trgm_into_ext_schema(db_url: str) -> None:
    """pg_trgm lives in `ext`, not wherever `public` currently points."""
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT nspname FROM pg_extension "
            "JOIN pg_namespace "
            "  ON pg_namespace.oid = pg_extension.extnamespace "
            "WHERE extname = 'pg_trgm'"
        ).fetchone()

    assert row == ("ext",)


def test_schema_has_no_loaded_at_columns(db_url: str) -> None:
    """loaded_at (cross-run purge machinery) no longer exists."""
    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE column_name = 'loaded_at'"
        ).fetchall()

    assert rows == []


_SCHEMA_SQL_FILE = Path(__file__).resolve().parents[3] / "db" / "schema.sql"


def test_rebuild_schema_creates_loading_with_deferred_indexes_dropped(
    db_url: str,
) -> None:
    """Verify loading schema is created with deferred indexes dropped.

    Loading gets every table from schema.sql, but its five bulk
    indexes/constraint are already gone, ready for a fast COPY.
    """
    schema_sql = _SCHEMA_SQL_FILE.read_text(encoding="utf-8")
    with psycopg.connect(db_url, autocommit=True) as conn:
        cursor = conn.cursor()
        _rebuild_schema(cursor, schema_sql)

        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'loading' ORDER BY table_name"
        ).fetchall()
        indexes = conn.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = 'loading' "
            "AND indexname = 'lexeme_natural_key'"
        ).fetchall()

    assert ("lexeme",) in tables
    assert ("stg_lexeme",) in tables
    assert indexes == []


_ANCESTOR = Lexeme(
    lang_code="ine-pro",
    headword="leǵ-",
    is_reconstructed=True,
    source_ref="wiktionary:2026-06-01:ine-pro:leǵ-",
)


def _etymology(  # ruff: ignore[too-many-arguments] - test builder, one kwarg per Lexeme field
    *,
    gloss: str | None = None,
    pos: str | None = None,
    etymology_number: str | None = None,
    romanization: str | None = None,
    is_reconstructed: bool = False,
    is_redlink: bool = False,
    source_ref: str = "w:0",
) -> Lexeme:
    """Build an en "etymology" lexeme, wrapping pos/gloss into a Sense.

    Mirrors an entry's shape post-fix: pos/gloss live on a Sense, while
    lexeme identity is lang_code/headword/etymology_number.

    Returns:
        The built Lexeme.
    """
    senses = (
        (Sense(pos=pos, gloss=gloss, source_ref=source_ref),)
        if pos is not None or gloss is not None
        else ()
    )
    return Lexeme(
        lang_code="en",
        headword="etymology",
        etymology_number=etymology_number,
        romanization=romanization,
        is_reconstructed=is_reconstructed,
        is_redlink=is_redlink,
        source_ref=source_ref,
        senses=senses,
    )


def _edge(dst: Lexeme) -> EtymEdge:
    return EtymEdge(
        src=_ANCESTOR,
        dst=dst,
        rel_type=RelType.INHERITED,
        source_ref="wiktionary:2026-06-01:edge",
    )


def test_load_edges_rejects_a_database_missing_the_ext_migration(
    db_url: str,
) -> None:
    """pg_trgm outside `ext` fails fast, naming the migration to apply.

    Simulates a database built by replaying migrations up to 0009: the
    trgm index DDL in schema.sql would otherwise blow up on an
    unresolvable `ext.gin_trgm_ops` partway through the rebuild.
    """
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("ALTER EXTENSION pg_trgm SET SCHEMA public")

    with pytest.raises(RuntimeError, match="0010_ext_schema"):
        load_edges(db_url, [_edge(_etymology(source_ref="w:1"))])


def test_set_search_path_raises_when_it_does_not_take_effect(
    db_url: str,
) -> None:
    """An unresolvable search_path raises instead of falling back.

    Guards the one way a pooled connection could route the bare SET and
    the writes after it to different backends, silently landing the
    reload's writes in `public`.
    """
    with (
        psycopg.connect(db_url, autocommit=True) as conn,
        conn.cursor() as cursor,
        pytest.raises(RuntimeError, match="search_path"),
    ):
        _set_search_path_or_raise(cursor, "schema_that_does_not_exist")
