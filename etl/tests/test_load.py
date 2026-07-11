"""DB-backed tests for the loader's upsert behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg

from etymyriad.load import _ensure_languages, load_edges
from etymyriad.model import EtymEdge, Lexeme, RelType

if TYPE_CHECKING:
    from collections.abc import Iterable

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


def test_upsert_latest_wins_within_same_chunk(db_url: str) -> None:
    """Two edges to the same lexeme in one batch still resolve latest-wins."""
    edges = [
        _edge(_water(pos=None, source_ref="w:1")),
        _edge(_water(pos="noun", source_ref="w:2")),
    ]

    load_edges(db_url, edges)

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT pos, source_ref FROM lexeme WHERE headword = 'water'"
        ).fetchone()

    assert row is not None
    assert row[0] == "noun"
    assert row[1] == "w:2"


def test_upsert_latest_wins_across_chunk_boundary(db_url: str) -> None:
    """Latest-wins coalesce holds across a chunk-commit boundary too."""
    edges = [
        _edge(_water(pos=None, source_ref="w:1")),
        _edge(_water(pos="noun", source_ref="w:2")),
    ]

    load_edges(db_url, edges, chunk_size=1)

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT pos, source_ref FROM lexeme WHERE headword = 'water'"
        ).fetchone()

    assert row is not None
    assert row[0] == "noun"
    assert row[1] == "w:2"


class _FakeCursor:
    """Records executemany calls without touching a real database."""

    def __init__(self) -> None:
        self.calls: list[list[tuple[str, str, bool]]] = []

    def executemany(
        self,
        _query: str,
        rows: Iterable[tuple[str, str, bool]],
    ) -> None:
        self.calls.append(list(rows))


def test_ensure_languages_skips_already_seen_codes() -> None:
    """A language code already loaded this run is never re-inserted."""
    cursor = _FakeCursor()
    seen = {"ine-pro"}
    edge = _edge(_water(source_ref="w:1"))

    _ensure_languages(cursor, [edge], seen)  # ty: ignore[invalid-argument-type]

    assert cursor.calls == [[("en", "en", False)]]
    assert seen == {"ine-pro", "en"}


def test_ensure_languages_marks_proto_language_codes() -> None:
    """A '-pro'-suffixed code is seeded with is_proto true."""
    cursor = _FakeCursor()
    edge = _edge(_water(source_ref="w:1"))

    _ensure_languages(cursor, [edge], set())  # ty: ignore[invalid-argument-type]

    assert ("ine-pro", "ine-pro", True) in cursor.calls[0]
    assert ("en", "en", False) in cursor.calls[0]


def test_ensure_languages_inserts_nothing_when_all_seen() -> None:
    """A chunk with no new language codes issues no insert at all."""
    cursor = _FakeCursor()
    seen = {"ine-pro", "en"}
    edge = _edge(_water(source_ref="w:1"))

    _ensure_languages(cursor, [edge], seen)  # ty: ignore[invalid-argument-type]

    assert cursor.calls == []
