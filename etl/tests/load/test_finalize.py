"""Tests for finalizing, gating, and swapping a merged generation."""

from typing import TYPE_CHECKING

import psycopg
import pytest

from etymyriad.load import load_edges
from etymyriad.load._finalize import (
    _check_unknown_languages_or_raise,
)
from etymyriad.load._merge import MergeCounts
from etymyriad.model import EtymEdge, RelType, Sense, Term

if TYPE_CHECKING:
    from collections.abc import Iterator


def _terms(count: int) -> Iterator[Term]:
    for index in range(count):
        yield Term("en", f"w{index}", senses=(Sense("noun", "x"),))


def _unknown_language_edge() -> EtymEdge:
    return EtymEdge(
        Term("zzz-notacode", "x"),
        Term("en", "y", senses=(Sense("noun", "x"),)),
        RelType.INHERITED,
        anchor="etymology_templates:0:inh",
    )


def test_pickable_terms_skip_redlinks_and_mention_only_terms(
    db_url: str,
) -> None:
    """Redlinks and mention-only terms stay out of `pickable_term`."""
    real = Term("en", "aqua", senses=(Sense("noun", "water"),))
    mentioned = Term("en", "drop", senses=(Sense("noun", "x"),))
    load_edges(
        db_url,
        [
            EtymEdge(
                Term("la", "aqua"),
                real,
                RelType.BORROWED,
                anchor="etymology_templates:0:bor",
            ),
            EtymEdge(
                Term("la", "gutta"),
                mentioned,
                RelType.MENTION,
                anchor="etymology_templates:0:m",
            ),
        ],
        dump_date="2026-09-02",
    )
    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            """
            SELECT t.headword FROM pickable_term p
            JOIN term t ON t.id = p.term_id
            """
        ).fetchall()
    assert rows == [("aqua",)]


def test_unknown_language_share_gate() -> None:
    """More than 0.1% unknown-language edges refuses the load."""
    _check_unknown_languages_or_raise(MergeCounts(10_000, 10))
    with pytest.raises(RuntimeError, match="unknown language"):
        _check_unknown_languages_or_raise(MergeCounts(10_000, 11))


def test_failed_load_drops_the_loading_schema(db_url: str) -> None:
    """A refused load leaves no `loading` copy behind."""
    load_edges(db_url, _terms(100), dump_date="2026-09-02")
    with pytest.raises(RuntimeError, match="unknown language"):
        load_edges(db_url, [_unknown_language_edge()], dump_date="2026-10-01")
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT count(*) FROM pg_namespace WHERE nspname = 'loading'"
        ).fetchone()
    assert row == (0,)


def test_cleanup_failure_does_not_mask_the_original_error(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing cleanup does not hide the error that caused it."""

    def _failing_edges() -> Iterator[Term]:
        yield from _terms(1)
        msg = "original"
        raise RuntimeError(msg)

    def _broken_cleanup(_database_url: str) -> None:
        msg = "cleanup"
        raise OSError(msg)

    monkeypatch.setattr(
        "etymyriad.load._load._drop_loading_schema", _broken_cleanup
    )
    with pytest.raises(RuntimeError, match="original"):
        load_edges(db_url, _failing_edges(), dump_date="2026-09-02")
