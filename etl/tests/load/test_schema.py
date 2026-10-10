"""Tests for the schema DDL and its migration baseline."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

_SCHEMA = Path(__file__).resolve().parents[3] / "db" / "schema.sql"
_BASELINE = _SCHEMA.parent / "migrations" / "0001_baseline.sql"


def test_baseline_migration_mirrors_schema() -> None:
    """The only migration is a byte-for-byte copy of schema.sql."""
    migrations = sorted(_BASELINE.parent.glob("*.sql"))
    assert migrations == [_BASELINE]
    assert _BASELINE.read_text() == _SCHEMA.read_text()


def test_source_ref_formats_citations(db_url: str) -> None:
    """source_ref() builds the citation from the dataset dump date."""
    with psycopg.connect(db_url) as conn:
        conn.execute("INSERT INTO dataset (dump_date) VALUES ('2026-09-02')")
        row = conn.execute(
            "SELECT source_ref('en', 'aqua'),"
            " source_ref('en', 'aqua', 'etymology_templates:0:bor'),"
            " source_ref('en', 'bank', 'etymology_templates:0:inh', 2)"
        ).fetchone()
    assert row == (
        "wiktionary:2026-09-02:en:aqua",
        "wiktionary:2026-09-02:en:aqua#etymology_templates:0:bor",
        "wiktionary:2026-09-02:en:bank:2#etymology_templates:0:inh",
    )


def test_edge_rejects_a_same_term_edge(db_url: str) -> None:
    """An edge from a term to itself violates the self-loop check."""
    with psycopg.connect(db_url) as conn:
        conn.execute(
            "INSERT INTO language (code, name, kind)"
            " VALUES ('en', 'English', 'regular')"
        )
        conn.execute(
            "INSERT INTO term (language_id, headword) VALUES (1, 'bank')"
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO edge (src_term_id, dst_term_id, dst_section,"
                " rel_type, anchor) VALUES (1, 1, 2, 'derived', 'x')"
            )


def test_dataset_holds_one_row(db_url: str) -> None:
    """A second dataset row violates the singleton key."""
    with psycopg.connect(db_url) as conn:
        conn.execute("INSERT INTO dataset (dump_date) VALUES ('2026-09-02')")
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(
                "INSERT INTO dataset (dump_date) VALUES ('2026-10-01')"
            )


def test_no_extension_schema(db_url: str) -> None:
    """The schema creates no `ext` namespace."""
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT count(*) FROM pg_namespace WHERE nspname = 'ext'"
        ).fetchone()
    assert row == (0,)
