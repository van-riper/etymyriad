"""End-to-end tests for the `load_edges` orchestrator."""

from __future__ import annotations

import logging

import psycopg
import pytest

from etymyriad.load import load_edges
from etymyriad.load._load import _log_progress
from etymyriad.load._schema import _LOAD_LOCK_KEY
from etymyriad.model import EtymEdge, RelType, Sense, Term

_EDGE = EtymEdge(
    Term("la", "aqua"),
    Term("en", "aqua", senses=(Sense("noun", "water"),)),
    RelType.BORROWED,
    anchor="etymology_templates:0:bor",
)


def test_log_progress_uses_thousands_separators(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A large count reads as "10,287,531"."""
    with caplog.at_level(logging.INFO, logger="etymyriad.load"):
        _log_progress(10_287_531)
    assert "10,287,531" in caplog.records[0].message


def test_load_edges_runs_full_pipeline_and_returns_edge_count(
    db_url: str,
) -> None:
    """One call stages, merges, finalizes, and swaps.

    The count is the edges that landed, so a duplicate edge and a lone
    term add nothing to it.
    """
    count = load_edges(
        db_url,
        [_EDGE, _EDGE, Term("en", "con", senses=(Sense("noun", "x"),))],
        dump_date="2026-09-02",
    )
    assert count == 1
    with psycopg.connect(db_url) as conn:
        headwords = {
            row[0] for row in conn.execute("SELECT headword FROM term")
        }
    assert headwords == {"aqua", "con"}


def test_load_edges_refuses_to_swap_an_empty_graph(db_url: str) -> None:
    """Staging nothing never replaces a live graph."""
    load_edges(db_url, [_EDGE], dump_date="2026-09-02")
    with pytest.raises(ValueError, match="empty graph"):
        load_edges(db_url, [], dump_date="2026-09-02")
    with psycopg.connect(db_url) as conn:
        row = conn.execute("SELECT count(*) FROM term").fetchone()
    assert row == (2,)


def test_load_edges_rejects_a_concurrent_run(db_url: str) -> None:
    """A second load fails fast instead of racing the first."""
    with psycopg.connect(db_url, autocommit=True) as holder:
        holder.execute("SELECT pg_advisory_lock(%s)", (_LOAD_LOCK_KEY,))
        with pytest.raises(RuntimeError, match="already in progress"):
            load_edges(db_url, [_EDGE], dump_date="2026-09-02")
