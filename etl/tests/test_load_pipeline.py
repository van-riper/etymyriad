"""End-to-end tests for the `load_edges` orchestrator."""

from __future__ import annotations

import logging

import psycopg
import pytest

from etymyriad.load import load_edges
from etymyriad.load._load import _log_progress
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


def test_log_progress_uses_thousands_separators(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A large count reads as "10,287,531", not "10287531"."""
    with caplog.at_level(logging.INFO, logger="etymyriad.load"):
        _log_progress(10_287_531)

    message = caplog.records[0].message
    assert "10,287,531" in message


def test_load_edges_runs_full_pipeline_and_returns_count(
    db_url: str,
) -> None:
    """One call stages, merges, fixes up, indexes, and swaps."""
    edges = [
        _edge(_etymology(pos="noun", gloss="H2O", source_ref="w:1")),
        Lexeme(lang_code="en", headword="con", source_ref="w:lone"),
    ]

    count = load_edges(db_url, edges)

    assert count == 2
    with psycopg.connect(db_url) as conn:
        headwords = {
            row[0]
            for row in conn.execute("SELECT headword FROM lexeme").fetchall()
        }
    assert headwords == {"etymology", "leǵ-", "con"}


def test_load_edges_refuses_to_swap_an_empty_graph(db_url: str) -> None:
    """Staging nothing is a bug upstream, never a graph worth promoting."""
    load_edges(db_url, [_edge(_etymology(source_ref="w:1"))])

    with pytest.raises(ValueError, match="empty graph"):
        load_edges(db_url, [])

    with psycopg.connect(db_url) as conn:
        headwords = {
            row[0]
            for row in conn.execute("SELECT headword FROM lexeme").fetchall()
        }

    assert headwords == {"etymology", "leǵ-"}


def test_load_edges_backtraces_a_real_ancestry_chain(db_url: str) -> None:
    """The canonical recursive-CTE backtrace from CLAUDE.md holds.

    A real run resolves etymology (en) -> etymologia (la) ->
    etymologia (grc).
    """
    grc = Lexeme(lang_code="grc", headword="ἐτυμολογία", source_ref="w:grc")
    la = Lexeme(lang_code="la", headword="etymologia", source_ref="w:la")
    en = _etymology(source_ref="w:en")
    edges = [
        EtymEdge(src=grc, dst=la, rel_type=RelType.BORROWED, source_ref="w:1"),
        EtymEdge(src=la, dst=en, rel_type=RelType.BORROWED, source_ref="w:2"),
    ]

    load_edges(db_url, edges)

    with psycopg.connect(db_url) as conn:
        rows = conn.execute("""
            WITH RECURSIVE ancestors AS (
                SELECT e.src_id, e.dst_id, 1 AS depth
                FROM etymology e
                JOIN lexeme d ON d.id = e.dst_id
                WHERE d.headword = 'etymology'
              UNION ALL
                SELECT e.src_id, e.dst_id, a.depth + 1
                FROM etymology e
                JOIN ancestors a ON e.dst_id = a.src_id
            )
            SELECT l.headword FROM ancestors a
            JOIN lexeme l ON l.id = a.src_id
            ORDER BY a.depth
        """).fetchall()

    assert [row[0] for row in rows] == ["etymologia", "ἐτυμολογία"]
