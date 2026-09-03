"""Tests for the atomic blue/green schema swap."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import psycopg
import psycopg.errors
import pytest

from etymyriad.load import load_edges
from etymyriad.load._schema import _ROLLBACK_SCHEMA, _TARGET_SCHEMA
from etymyriad.load._swap import _swap_schemas
from etymyriad.model import EtymEdge, Lexeme, RelType, Sense

if TYPE_CHECKING:
    from collections.abc import Iterable

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


def test_load_edges_leaves_public_untouched_on_a_failed_run(
    db_url: str,
) -> None:
    """A run that fails before the swap leaves `public` untouched.

    Nothing about the failed run's `loading` schema ever reached it.
    """
    load_edges(db_url, [_edge(_etymology(source_ref="w:1"))])

    def _broken_edges() -> Iterable[EtymEdge]:
        yield _edge(_etymology(etymology_number="2", source_ref="w:2"))
        msg = "boom"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="boom"):
        load_edges(db_url, _broken_edges())

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT etymology_number FROM lexeme WHERE headword = 'etymology'"
        ).fetchall()

    assert rows == [(None,)]


def test_load_edges_keeps_one_rollback_generation(db_url: str) -> None:
    """Two runs leave the first run's graph in public_old."""
    load_edges(db_url, [_edge(_etymology(source_ref="w:1"))])
    load_edges(
        db_url,
        [_edge(_etymology(etymology_number="2", source_ref="w:2"))],
    )

    with psycopg.connect(db_url) as conn:
        current = conn.execute(
            "SELECT etymology_number FROM lexeme WHERE headword = 'etymology'"
        ).fetchall()
        rolled_back = conn.execute(
            "SELECT etymology_number FROM public_old.lexeme "
            "WHERE headword = 'etymology'"
        ).fetchall()

    assert current == [("2",)]
    assert rolled_back == [(None,)]


def test_swap_schemas_promotes_loading_and_keeps_one_rollback_gen(
    db_url: str,
) -> None:
    """First swap demotes previous public to public_old and promotes loading.

    Verifies atomic schema promotion: `loading` becomes `public`,
    `public` becomes `public_old`, and only one rollback generation
    is preserved (any prior `public_old` is dropped).
    """
    with psycopg.connect(db_url, autocommit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(f"DROP SCHEMA IF EXISTS {_TARGET_SCHEMA} CASCADE")
        cursor.execute(f"CREATE SCHEMA {_TARGET_SCHEMA}")
        cursor.execute(f"CREATE TABLE {_TARGET_SCHEMA}.marker (gen int)")
        cursor.execute(f"INSERT INTO {_TARGET_SCHEMA}.marker VALUES (1)")
        _swap_schemas(conn)

        gen_one = conn.execute("SELECT gen FROM public.marker").fetchone()
        rollback_exists = conn.execute(
            "SELECT 1 FROM information_schema.schemata "
            f"WHERE schema_name = '{_ROLLBACK_SCHEMA}'"
        ).fetchone()

        cursor.execute(f"CREATE SCHEMA {_TARGET_SCHEMA}")
        cursor.execute(f"CREATE TABLE {_TARGET_SCHEMA}.marker (gen int)")
        cursor.execute(f"INSERT INTO {_TARGET_SCHEMA}.marker VALUES (2)")
        _swap_schemas(conn)

        gen_two = conn.execute("SELECT gen FROM public.marker").fetchone()
        rollback_gen = conn.execute(
            f"SELECT gen FROM {_ROLLBACK_SCHEMA}.marker"
        ).fetchone()

    assert gen_one == (1,)
    assert rollback_exists is not None
    assert gen_two == (2,)
    assert rollback_gen == (1,)


def test_swap_schemas_fails_fast_on_a_contended_lock(db_url: str) -> None:
    """A held lock on public_old makes the swap raise, not hang.

    Confirms the `lock_timeout` set in `_swap_schemas` actually caps
    the wait on a conflicting lock, rather than the swap blocking
    indefinitely on a stuck reader.
    """
    with psycopg.connect(db_url, autocommit=True) as connection:
        cursor = connection.cursor()
        cursor.execute(f"CREATE SCHEMA {_TARGET_SCHEMA}")
        _swap_schemas(connection)  # seeds public_old from schema.sql's public

        cursor.execute(f"CREATE SCHEMA {_TARGET_SCHEMA}")

        with psycopg.connect(db_url) as blocker:
            blocker.execute(
                f"LOCK TABLE {_ROLLBACK_SCHEMA}.lexeme IN ACCESS EXCLUSIVE MODE"
            )

            started = time.monotonic()
            with pytest.raises(psycopg.errors.LockNotAvailable):
                _swap_schemas(connection)
            elapsed_seconds = time.monotonic() - started

    assert elapsed_seconds < 10
