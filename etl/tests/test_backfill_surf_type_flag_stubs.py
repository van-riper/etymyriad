"""DB-backed tests for the {{surf}} "+type"-flag stub backfill.

`scripts/backfill_surf_type_flag_stubs.py` sits outside the
`etymyriad` package (see pyproject.toml's `scripts/*.py` lint
carve-out), so it is loaded here by file path rather than a normal
import.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import psycopg

if TYPE_CHECKING:
    from types import ModuleType

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "backfill_surf_type_flag_stubs.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "backfill_surf_type_flag_stubs", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill_surf_type_flag_stubs = _load_script()


def _insert_lexeme(
    conn: psycopg.Connection,
    *,
    lang_code: str = "en",
    headword: str,
    source_ref: str | None = None,
) -> str:
    conn.execute(
        "INSERT INTO language (code, name) VALUES (%s, %s) "
        "ON CONFLICT (code) DO NOTHING",
        (lang_code, lang_code),
    )
    row = conn.execute(
        "INSERT INTO lexeme (lang_code, headword, source_ref) "
        "VALUES (%s, %s, %s) RETURNING id::text",
        (
            lang_code,
            headword,
            source_ref or f"wiktionary:2026-06-01:{lang_code}:{headword}",
        ),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_edge(
    conn: psycopg.Connection,
    *,
    src_id: str,
    dst_id: str,
    rel_type: str = "surface_analysis",
    piece_order: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO etymology (src_id, dst_id, rel_type, source_ref, "
        "piece_order) VALUES (%s, %s, %s, 'w:0', %s)",
        (src_id, dst_id, rel_type, piece_order),
    )


def _lexeme_row(
    conn: psycopg.Connection, lexeme_id: str
) -> tuple[str, str, str] | None:
    return conn.execute(
        "SELECT lang_code, headword, source_ref FROM lexeme WHERE id = %s",
        (lexeme_id,),
    ).fetchone()


def _etymology_count(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM etymology").fetchone()
    assert row is not None
    return row[0]


def test_no_piece_flag_is_dropped_with_its_edges(db_url: str) -> None:
    """A "+onom"/"+lit" stub is deleted outright, not renamed or merged."""
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, headword="chichot")
        stub = _insert_lexeme(conn, lang_code="+onom", headword="pl")
        _insert_edge(conn, src_id=stub, dst_id=dst)
        conn.commit()

    stats = backfill_surf_type_flag_stubs.backfill(db_url, execute=True)

    assert stats.dropped == 1
    assert stats.merged == stats.renamed == stats.ambiguous == stats.unsafe == 0
    with psycopg.connect(db_url) as conn:
        assert _lexeme_row(conn, stub) is None
        assert _etymology_count(conn) == 0


def test_renames_stub_cited_by_one_language(db_url: str) -> None:
    """A stub cited by exactly one language renames onto it in place."""
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, headword="community")
        stub = _insert_lexeme(
            conn,
            lang_code="+suf",
            headword="ity",
            source_ref="wiktionary:2026-06-01:+suf:ity",
        )
        _insert_edge(conn, src_id=stub, dst_id=dst)
        conn.commit()

    stats = backfill_surf_type_flag_stubs.backfill(db_url, execute=True)

    assert stats.renamed == 1
    assert stats.dropped == stats.merged == stats.ambiguous == stats.unsafe == 0
    with psycopg.connect(db_url) as conn:
        row = _lexeme_row(conn, stub)
        assert row == ("en", "ity", "wiktionary:2026-06-01:en:ity")


def test_merges_stub_onto_existing_real_target(db_url: str) -> None:
    """A stub whose real (lang, headword) already exists merges onto it."""
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="commune")
        dst = _insert_lexeme(conn, headword="community")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="commune")
        _insert_edge(conn, src_id=stub, dst_id=dst)
        conn.commit()

    stats = backfill_surf_type_flag_stubs.backfill(db_url, execute=True)

    assert stats.merged == 1
    assert (
        stats.dropped == stats.renamed == stats.ambiguous == stats.unsafe == 0
    )
    with psycopg.connect(db_url) as conn:
        assert _lexeme_row(conn, stub) is None
        edge = conn.execute(
            "SELECT src_id::text, dst_id::text FROM etymology"
        ).fetchone()
        assert edge == (real, dst)


def test_merge_preserves_piece_order(db_url: str) -> None:
    """A merged surface_analysis edge keeps its piece_order, not NULL."""
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="commune")
        dst = _insert_lexeme(conn, headword="community")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="commune")
        _insert_edge(conn, src_id=stub, dst_id=dst, piece_order=2)
        conn.commit()

    stats = backfill_surf_type_flag_stubs.backfill(db_url, execute=True)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        edge = conn.execute(
            "SELECT src_id::text, piece_order FROM etymology"
        ).fetchone()
        assert edge == (real, 2)


def test_stub_cited_by_two_languages_is_ambiguous(db_url: str) -> None:
    """A stub cited by more than one distinct language is left untouched."""
    with psycopg.connect(db_url) as conn:
        en_dst = _insert_lexeme(conn, lang_code="en", headword="community")
        pl_dst = _insert_lexeme(conn, lang_code="pl", headword="inny")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="ity")
        _insert_edge(conn, src_id=stub, dst_id=en_dst)
        _insert_edge(conn, src_id=stub, dst_id=pl_dst)
        conn.commit()

    stats = backfill_surf_type_flag_stubs.backfill(db_url, execute=True)

    assert stats.ambiguous == 1
    assert stats.dropped == stats.merged == stats.renamed == stats.unsafe == 0
    with psycopg.connect(db_url) as conn:
        assert _lexeme_row(conn, stub) == (
            "+suf",
            "ity",
            "wiktionary:2026-06-01:+suf:ity",
        )


def test_merge_target_with_own_senses_is_unsafe(db_url: str) -> None:
    """A real merge target already carrying senses is skipped, not merged."""
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="commune")
        dst = _insert_lexeme(conn, headword="community")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="commune")
        conn.execute(
            "INSERT INTO sense (lexeme_id, source_ref) VALUES (%s, 'w:0')",
            (stub,),
        )
        _insert_edge(conn, src_id=stub, dst_id=dst)
        conn.commit()

    stats = backfill_surf_type_flag_stubs.backfill(db_url, execute=True)

    assert stats.unsafe == 1
    assert (
        stats.dropped == stats.merged == stats.renamed == stats.ambiguous == 0
    )
    with psycopg.connect(db_url) as conn:
        assert _lexeme_row(conn, stub) is not None
        assert real is not None


def test_merge_skips_edge_colliding_with_an_existing_one(db_url: str) -> None:
    """A repoint duplicating an existing edge is skipped, not raised."""
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="commune")
        dst = _insert_lexeme(conn, headword="community")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="commune")
        _insert_edge(conn, src_id=real, dst_id=dst)
        _insert_edge(conn, src_id=stub, dst_id=dst)
        conn.commit()

    stats = backfill_surf_type_flag_stubs.backfill(db_url, execute=True)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert _etymology_count(conn) == 1


def test_dry_run_makes_no_changes(db_url: str) -> None:
    """Without --execute (execute=False), the transaction rolls back."""
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, headword="community")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="ity")
        _insert_edge(conn, src_id=stub, dst_id=dst)
        conn.commit()

    stats = backfill_surf_type_flag_stubs.backfill(db_url, execute=False)

    assert stats.renamed == 1
    with psycopg.connect(db_url) as conn:
        assert _lexeme_row(conn, stub) == (
            "+suf",
            "ity",
            "wiktionary:2026-06-01:+suf:ity",
        )
