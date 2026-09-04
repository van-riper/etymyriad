"""Tests for streaming edges/lexemes into the staging tables."""

from __future__ import annotations

import psycopg
import pytest

from etymyriad.load import load_edges
from etymyriad.load._schema import _STAGING_DDL_SQL, _TARGET_SCHEMA
from etymyriad.load._staging import _stage_items
from etymyriad.model import EtymEdge, Lexeme, RelType, Sense

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


def test_load_inserts_a_lone_lexeme_with_no_edges(db_url: str) -> None:
    """A zero-edge entry's own lexeme+senses load with no etymology row.

    Real record: en "con" etymology 3 ("Clipping of confidence trick")
    has a real sense but no ancestor-asserting template, so
    normalize() yields its lexeme on its own, not as an edge endpoint
    The loader must upsert it from that lone lexeme alone.
    """
    lexeme = _etymology(pos="noun", gloss="A confidence trick.")

    load_edges(db_url, [lexeme])

    with psycopg.connect(db_url) as conn:
        lexeme_row = conn.execute(
            "SELECT id FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()
        assert lexeme_row is not None
        sense_row = conn.execute(
            "SELECT gloss FROM sense WHERE lexeme_id = %s", (lexeme_row[0],)
        ).fetchone()
        edge_count = conn.execute("SELECT count(*) FROM etymology").fetchone()

    assert sense_row is not None
    assert sense_row[0] == "A confidence trick."
    assert edge_count is not None
    assert edge_count[0] == 0


def test_load_mixes_lone_lexemes_and_edges_in_one_chunk(db_url: str) -> None:
    """A chunk with both a lone lexeme and a real edge loads both."""
    lone = Lexeme(lang_code="en", headword="con", source_ref="w:lone")
    edge = _edge(_etymology(source_ref="w:1"))

    load_edges(db_url, [lone, edge])

    with psycopg.connect(db_url) as conn:
        headwords = {
            row[0]
            for row in conn.execute("SELECT headword FROM lexeme").fetchall()
        }

    assert headwords == {"con", "etymology", "leǵ-"}


def _make_loading_schema(db_url: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA {_TARGET_SCHEMA}")
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        conn.execute(_STAGING_DDL_SQL)


def test_stage_items_writes_lexeme_and_edge_rows(db_url: str) -> None:
    """Edges write two endpoint rows plus one edge row.

    Lone lexemes write only their own row.
    """
    _make_loading_schema(db_url)
    lone = Lexeme(lang_code="en", headword="con", source_ref="w:lone")
    edge = _edge(_etymology(pos="noun", source_ref="w:1"))

    count, languages = _stage_items(db_url, [lone, edge])

    assert count == 2
    assert languages == {"en", "ine-pro"}
    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        lex_rows = conn.execute(
            "SELECT headword, pos, has_sense FROM stg_lexeme ORDER BY headword"
        ).fetchall()
        edge_rows = conn.execute("SELECT count(*) FROM stg_edge").fetchone()

    assert lex_rows == [
        ("con", None, False),
        ("etymology", "noun", True),
        ("leǵ-", None, False),
    ]
    assert edge_rows == (1,)


def test_stage_items_rejects_a_lexeme_with_more_than_one_sense(
    db_url: str,
) -> None:
    """Staging assumes normalize() never attaches >1 sense; reject >1.

    Uses a real `db_url` (with `loading` already built): `_stage_items`
    opens its two COPY connections before it ever inspects an item, so
    a bogus DSN or a missing `loading.stg_lexeme` table would fail at
    connect/copy-open time, before reaching the validation this test
    means to exercise. A future violation must fail loudly, not silently
    drop a sense row.
    """
    _make_loading_schema(db_url)
    two_senses = Lexeme(
        lang_code="en",
        headword="reverse",
        source_ref="w:1",
        senses=(
            Sense(pos="adj", source_ref="w:1"),
            Sense(pos="noun", source_ref="w:1"),
        ),
    )

    with pytest.raises(ValueError, match="senses"):
        _stage_items(db_url, [two_senses])
