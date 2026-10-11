"""Tests for streaming terms and edges into the staging tables."""

from __future__ import annotations

import logging
from pathlib import Path

import psycopg
import pytest

from etymyriad.load._schema import _rebuild_schema
from etymyriad.load._staging import _stage_items
from etymyriad.model import EtymEdge, RelType, Sense, Term

_SCHEMA_SQL_PATH = Path(__file__).resolve().parents[3] / "db" / "schema.sql"


def _rebuild(db_url: str) -> None:
    schema_sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    with psycopg.connect(db_url, autocommit=True) as conn:
        _rebuild_schema(conn.cursor(), schema_sql)


def test_stages_an_edge_and_both_terms(db_url: str) -> None:
    """An edge writes both endpoint terms and one edge row."""
    edge = EtymEdge(
        src=Term("la", "aqua", variety_code="la-lat"),
        dst=Term("en", "aqua", section=2, senses=(Sense("noun", "water"),)),
        rel_type=RelType.BORROWED,
        anchor="etymology_templates:0:bor",
    )
    _rebuild(db_url)
    count, codes = _stage_items(db_url, [edge])
    assert (count, codes) == (1, {"la", "la-lat", "en"})
    with psycopg.connect(db_url) as conn:
        terms = conn.execute(
            "SELECT lang_code, headword, section, part_of_speech, gloss,"
            " has_sense FROM loading.stg_term ORDER BY lang_code"
        ).fetchall()
        edges = conn.execute(
            "SELECT src_variety_code, dst_section, anchor FROM loading.stg_edge"
        ).fetchall()
    assert terms == [
        ("en", "aqua", 2, "noun", "water", True),
        ("la", "aqua", 0, None, None, False),
    ]
    assert edges == [("la-lat", 2, "etymology_templates:0:bor")]


def test_rejects_a_term_with_two_senses(db_url: str) -> None:
    """Staging refuses a term that carries more than one sense."""
    _rebuild(db_url)
    term = Term("en", "a", senses=(Sense("noun", "x"), Sense("verb", "y")))
    with pytest.raises(ValueError, match="senses"):
        _stage_items(db_url, [term])


def test_stage_items_progress_log_includes_a_rate(
    db_url: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The progress line shows items per second since the start."""
    clock = iter([0.0, 0.5])
    monkeypatch.setattr(
        "etymyriad.load._staging.time.monotonic", lambda: next(clock)
    )
    _rebuild(db_url)

    with caplog.at_level(logging.INFO, logger="etymyriad.load"):
        _stage_items(db_url, [Term("en", "a"), Term("en", "b")], log_every=2)

    assert "staged 2 items (4/sec)" in caplog.text
