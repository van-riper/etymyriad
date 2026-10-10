"""Tests for resolving staged natural keys into the final tables."""

from __future__ import annotations

from pathlib import Path
from typing import LiteralString

import psycopg

from etymyriad.load._merge import MergeCounts, _merge_staged_data
from etymyriad.load._schema import _rebuild_schema, _set_search_path_or_raise
from etymyriad.load._staging import _stage_items
from etymyriad.model import EtymEdge, RelType, Sense, Term

_SCHEMA = Path(__file__).resolve().parents[3] / "db" / "schema.sql"

_EN_AQUA = Term("en", "aqua", senses=(Sense("noun", "water"),))


def _merge(db_url: str, items: list[EtymEdge | Term]) -> MergeCounts:
    with psycopg.connect(db_url, autocommit=True) as conn:
        _rebuild_schema(conn.cursor(), _SCHEMA.read_text(encoding="utf-8"))
    _, codes = _stage_items(db_url, items)
    with psycopg.connect(db_url, autocommit=True) as conn:
        cur = conn.cursor()
        _set_search_path_or_raise(cur, "loading")
        return _merge_staged_data(cur, codes, "2026-09-02")


def _rows(db_url: str, sql: LiteralString) -> list[tuple[object, ...]]:
    with psycopg.connect(db_url) as conn:
        conn.execute("SET search_path TO loading")
        return conn.execute(sql).fetchall()


def test_variety_reference_merges_into_full_language_term(
    db_url: str,
) -> None:
    """A variety citation lands on the full language's term."""
    real_la = Term("la", "aqua", senses=(Sense("noun", "water"),))
    via_variety = EtymEdge(
        Term("la", "aqua", variety_code="la-lat"),
        _EN_AQUA,
        RelType.BORROWED,
        anchor="etymology_templates:0:bor",
    )
    _merge(db_url, [real_la, via_variety])
    assert _rows(
        db_url,
        """
        SELECT l.code, t.headword FROM term t
        JOIN language l ON l.id = t.language_id ORDER BY l.code
        """,
    ) == [("en", "aqua"), ("la", "aqua")]
    assert _rows(
        db_url,
        """
        SELECT v.code FROM edge e JOIN variety v ON v.id = e.src_variety_id
        """,
    ) == [("la-lat",)]


def test_real_entry_flag_beats_starred_variety_reference(
    db_url: str,
) -> None:
    """A real page's flag wins over a starred variety reference."""
    real_la = Term("la", "cantare", senses=(Sense("verb", "to sing"),))
    starred = EtymEdge(
        Term("la", "cantare", is_reconstructed=True, variety_code="roa-pro"),
        Term("en", "chant"),
        RelType.DERIVED,
        anchor="etymology_templates:0:der",
    )
    _merge(db_url, [real_la, starred])
    assert _rows(
        db_url,
        """
        SELECT t.is_reconstructed FROM term t
        JOIN language l ON l.id = t.language_id
        WHERE l.code = 'la' AND t.headword = 'cantare'
        """,
    ) == [(False,)]
    assert _rows(
        db_url,
        """
        SELECT v.code FROM edge e JOIN variety v ON v.id = e.src_variety_id
        """,
    ) == [("roa-pro",)]


def test_diacritic_stub_folds_into_its_unique_real_twin(
    db_url: str,
) -> None:
    """A macron-only redlink folds into its one real twin."""
    real = Term("la", "aqua", senses=(Sense("noun", "water"),))
    cited = EtymEdge(
        Term("la", "ăqua"),
        _EN_AQUA,
        RelType.BORROWED,
        anchor="etymology_templates:0:bor",
    )
    _merge(db_url, [real, cited])
    assert _rows(
        db_url,
        "SELECT s.headword FROM edge e JOIN term s ON s.id = e.src_term_id",
    ) == [("aqua",)]
    assert _rows(db_url, "SELECT count(*) FROM term") == [(2,)]


def test_reconstructed_stub_keeps_its_macron(db_url: str) -> None:
    """A reconstructed form's macron is never folded away."""
    real = Term(
        "ine-pro",
        "os",
        is_reconstructed=True,
        senses=(Sense("suffix", "x"),),
    )
    cited = EtymEdge(
        Term("ine-pro", "ōs", is_reconstructed=True),
        _EN_AQUA,
        RelType.ROOT,
        anchor="etymology_templates:0:root",
    )
    _merge(db_url, [real, cited])
    assert _rows(db_url, "SELECT count(*) FROM term") == [(3,)]


def test_sections_land_on_edge_and_sense(db_url: str) -> None:
    """Sections reach the edge and sense rows."""
    dst = Term("en", "bank", section=2, senses=(Sense("noun", "a slope"),))
    edge = EtymEdge(
        Term("non", "bakki"),
        dst,
        RelType.BORROWED,
        anchor="etymology_templates:0:bor",
    )
    _merge(db_url, [edge])
    assert _rows(db_url, "SELECT src_section, dst_section FROM edge") == [
        (0, 2)
    ]
    assert _rows(
        db_url, "SELECT section, part_of_speech, gloss FROM sense"
    ) == [(2, "noun", "a slope")]


def test_duplicate_edges_keep_the_lowest_anchor(db_url: str) -> None:
    """Duplicate edges collapse to the lowest anchor."""
    src = Term("la", "aqua")
    first = EtymEdge(
        src, _EN_AQUA, RelType.BORROWED, anchor="etymology_templates:2:bor"
    )
    again = EtymEdge(
        src, _EN_AQUA, RelType.BORROWED, anchor="etymology_templates:10:bor"
    )
    _merge(db_url, [again, first])
    assert _rows(db_url, "SELECT anchor FROM edge") == [
        ("etymology_templates:2:bor",)
    ]


def test_duplicate_edges_keep_one_templates_provenance(
    db_url: str,
) -> None:
    """The kept edge's variety comes from the template it cites."""
    lowest = EtymEdge(
        Term("la", "aqua"),
        _EN_AQUA,
        RelType.BORROWED,
        anchor="etymology_templates:0:bor",
    )
    higher = EtymEdge(
        Term("la", "aqua", variety_code="la-lat"),
        _EN_AQUA,
        RelType.BORROWED,
        anchor="etymology_templates:3:bor",
    )
    _merge(db_url, [higher, lowest])
    assert _rows(db_url, "SELECT anchor, src_variety_id FROM edge") == [
        ("etymology_templates:0:bor", None)
    ]


def test_unknown_language_edges_are_dropped_and_counted(
    db_url: str,
) -> None:
    """Edges with an unregistered language are dropped and counted."""
    edge = EtymEdge(
        Term("zzz-notacode", "x"),
        _EN_AQUA,
        RelType.DERIVED,
        anchor="etymology_templates:0:der",
    )
    counts = _merge(db_url, [edge])
    assert counts == MergeCounts(staged_edges=1, unknown_language_edges=1)
    assert _rows(db_url, "SELECT count(*) FROM edge") == [(0,)]


def test_dataset_records_the_dump_date(db_url: str) -> None:
    """The dataset row feeds source_ref the dump date."""
    _merge(db_url, [_EN_AQUA])
    assert _rows(db_url, "SELECT source_ref('en', 'aqua')") == [
        ("wiktionary:2026-09-02:en:aqua",)
    ]


def test_staging_tables_are_dropped(db_url: str) -> None:
    """No staging table survives the merge."""
    _merge(db_url, [_EN_AQUA])
    assert _rows(
        db_url,
        """
        SELECT count(*) FROM pg_tables
        WHERE schemaname = 'loading' AND tablename LIKE 'stg_%'
        """,
    ) == [(0,)]
