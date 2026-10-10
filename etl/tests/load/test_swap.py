"""Tests for the atomic blue/green schema swap."""

from __future__ import annotations

import time

import psycopg
import psycopg.errors
import pytest

from etymyriad.load import load_edges
from etymyriad.load._schema import _TARGET_SCHEMA
from etymyriad.load._swap import _swap_schemas
from etymyriad.model import Sense, Term


def _terms(count: int) -> list[Term]:
    return [
        Term("en", f"w{index}", senses=(Sense("noun", "x"),))
        for index in range(count)
    ]


def test_swap_replaces_public_and_keeps_no_old_copy(db_url: str) -> None:
    """A swap leaves only `public`, with no rollback schema."""
    load_edges(db_url, _terms(3), dump_date="2026-09-02")
    load_edges(db_url, _terms(3), dump_date="2026-09-02")
    with psycopg.connect(db_url) as conn:
        schemas = {
            row[0]
            for row in conn.execute(
                "SELECT nspname FROM pg_namespace"
                " WHERE nspname IN ('public', 'public_old', 'loading')"
            )
        }
    assert schemas == {"public"}


def test_failed_gate_leaves_public_untouched(db_url: str) -> None:
    """A refused load keeps the live generation intact."""
    load_edges(db_url, _terms(100), dump_date="2026-09-02")
    with pytest.raises(RuntimeError):
        load_edges(db_url, _terms(10), dump_date="2026-10-01")
    with psycopg.connect(db_url) as conn:
        row = conn.execute("SELECT source_ref('en', 'w0')").fetchone()
    assert row == ("wiktionary:2026-09-02:en:w0",)


def test_swap_schemas_promotes_loading(db_url: str) -> None:
    """The swap renames `loading` to `public`."""
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA {_TARGET_SCHEMA}")
        conn.execute(f"CREATE TABLE {_TARGET_SCHEMA}.marker (gen int)")
        conn.execute(f"INSERT INTO {_TARGET_SCHEMA}.marker VALUES (1)")
        _swap_schemas(conn)
        row = conn.execute("SELECT gen FROM public.marker").fetchone()
    assert row == (1,)


def test_swap_schemas_fails_fast_on_a_contended_lock(db_url: str) -> None:
    """A held lock makes the swap raise instead of hang."""
    with psycopg.connect(db_url, autocommit=True) as connection:
        connection.execute(f"CREATE SCHEMA {_TARGET_SCHEMA}")
        connection.execute("CREATE TABLE public.held (id int)")
        with psycopg.connect(db_url) as blocker:
            blocker.execute("LOCK TABLE public.held IN ACCESS EXCLUSIVE MODE")
            started = time.monotonic()
            with pytest.raises(psycopg.errors.LockNotAvailable):
                _swap_schemas(connection)
            elapsed_seconds = time.monotonic() - started
    assert elapsed_seconds < 10
