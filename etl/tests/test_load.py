"""DB-backed tests for the loader's upsert behavior."""

from __future__ import annotations

import psycopg

from etymyriad.load import load_edges
from etymyriad.model import EtymEdge, Lexeme, RelType

_ANCESTOR = Lexeme(
    lang_code="ine-pro",
    headword="wódr̥",
    is_reconstructed=True,
    source_ref="wiktionary:2026-06-01:ine-pro:wódr̥",
)


def _water(
    *,
    pos: str | None = None,
    romanization: str | None = None,
    is_reconstructed: bool = False,
    source_ref: str = "w:0",
) -> Lexeme:
    return Lexeme(
        lang_code="en",
        headword="water",
        pos=pos,
        romanization=romanization,
        is_reconstructed=is_reconstructed,
        source_ref=source_ref,
    )


def _edge(dst: Lexeme) -> EtymEdge:
    return EtymEdge(
        src=_ANCESTOR,
        dst=dst,
        rel_type=RelType.INHERITED,
        source_ref="wiktionary:2026-06-01:edge",
    )


def test_upsert_fills_pos_from_later_load(db_url: str) -> None:
    """A null pos loaded first is filled by a later load that has one."""
    load_edges(db_url, [_edge(_water(pos=None, source_ref="w:1"))])
    load_edges(db_url, [_edge(_water(pos="noun", source_ref="w:2"))])

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT pos, source_ref FROM lexeme WHERE headword = 'water'"
        ).fetchone()

    assert row is not None
    assert row[0] == "noun"  # richest value wins (coalesce)
    assert row[1] == "w:2"  # the citation always points at the latest load


def test_upsert_fills_romanization_from_later_load(db_url: str) -> None:
    """A null romanization loaded first is filled by a later load."""
    load_edges(db_url, [_edge(_water(romanization=None, source_ref="w:1"))])
    load_edges(db_url, [_edge(_water(romanization="water", source_ref="w:2"))])

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT romanization FROM lexeme WHERE headword = 'water'"
        ).fetchone()

    assert row is not None
    assert row[0] == "water"


def test_upsert_latches_reconstructed_from_later_load(db_url: str) -> None:
    """is_reconstructed latches true even if a plain load came first."""
    load_edges(
        db_url, [_edge(_water(is_reconstructed=False, source_ref="w:1"))]
    )
    load_edges(db_url, [_edge(_water(is_reconstructed=True, source_ref="w:2"))])

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT is_reconstructed FROM lexeme WHERE headword = 'water'"
        ).fetchone()

    assert row is not None
    assert row[0] is True
