"""DB-backed tests for the bound-morpheme-stub backfill.

`scripts/backfill_bound_morpheme_stubs.py` sits outside the `etymyriad`
package (see pyproject.toml's `scripts/*.py` lint carve-out), so it is
loaded here by file path rather than a normal import.
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
    / "backfill_bound_morpheme_stubs.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "backfill_bound_morpheme_stubs", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill_bound_morpheme_stubs = _load_script()


def _insert_lexeme(
    conn: psycopg.Connection,
    *,
    lang_code: str = "en",
    headword: str,
    etymology_number: str | None = None,
) -> str:
    conn.execute(
        "INSERT INTO language (code, name) VALUES (%s, %s) "
        "ON CONFLICT (code) DO NOTHING",
        (lang_code, lang_code),
    )
    row = conn.execute(
        "INSERT INTO lexeme (lang_code, headword, etymology_number, "
        "source_ref) VALUES (%s, %s, %s, 'w:0') RETURNING id::text",
        (lang_code, headword, etymology_number),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_edge(
    conn: psycopg.Connection, *, src_id: str, dst_id: str, rel_type: str
) -> None:
    conn.execute(
        "INSERT INTO etymology (src_id, dst_id, rel_type, source_ref) "
        "VALUES (%s, %s, %s, 'w:0')",
        (src_id, dst_id, rel_type),
    )


def _etymology_count(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM etymology").fetchone()
    assert row is not None
    return row[0]


def _lexeme_count(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM lexeme").fetchone()
    assert row is not None
    return row[0]


def test_merges_stub_into_its_one_numbered_sibling(db_url: str) -> None:
    """A senseless stub with exactly one numbered sibling merges into it.

    Real record: en "con" the bound morpheme, referenced by other
    entries' {{af}}/{{prefix}} templates, collapses onto a
    senseless etym_key='' stub that never merges with en "con"'s own
    numbered dictionary entry.
    """
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="con", etymology_number="1")
        stub = _insert_lexeme(conn, headword="con")
        other = _insert_lexeme(conn, headword="conjoin")
        _insert_edge(conn, src_id=stub, dst_id=other, rel_type="affix")
        conn.commit()

    stats = backfill_bound_morpheme_stubs.backfill(db_url, execute=True)

    assert stats.merged == 1
    assert stats.ambiguous == 0
    with psycopg.connect(db_url) as conn:
        edge = conn.execute(
            "SELECT src_id::text, dst_id::text FROM etymology"
        ).fetchone()
        assert edge == (real, other)
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (stub,)
            ).fetchone()
            is None
        )


def test_merge_skips_edge_that_would_become_a_self_loop(db_url: str) -> None:
    """An edge directly between the stub and its real self is dropped.

    Repointing both ends onto the same target would otherwise violate
    the etymology_no_self_loop check.
    """
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="con", etymology_number="1")
        stub = _insert_lexeme(conn, headword="con")
        _insert_edge(conn, src_id=stub, dst_id=real, rel_type="affix")
        conn.commit()

    stats = backfill_bound_morpheme_stubs.backfill(db_url, execute=True)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert _etymology_count(conn) == 0


def test_merge_drops_edge_colliding_with_an_existing_one(db_url: str) -> None:
    """A repoint duplicating an existing edge is skipped, not raised."""
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="con", etymology_number="1")
        stub = _insert_lexeme(conn, headword="con")
        other = _insert_lexeme(conn, headword="conjoin")
        _insert_edge(conn, src_id=real, dst_id=other, rel_type="affix")
        _insert_edge(conn, src_id=stub, dst_id=other, rel_type="affix")
        conn.commit()

    stats = backfill_bound_morpheme_stubs.backfill(db_url, execute=True)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert _etymology_count(conn) == 1


def test_ambiguous_match_is_left_untouched(db_url: str) -> None:
    """More than one numbered sibling is reported, not guessed at.

    Real record: en "con" carries two numbered etymologies (the
    convict/confidence-trick noun and the "with" prefix); a bound-
    morpheme reference to "con" can't tell which one it means.
    """
    with psycopg.connect(db_url) as conn:
        _insert_lexeme(conn, headword="con", etymology_number="1")
        _insert_lexeme(conn, headword="con", etymology_number="2")
        stub = _insert_lexeme(conn, headword="con")
        conn.commit()

    stats = backfill_bound_morpheme_stubs.backfill(db_url, execute=True)

    assert stats.ambiguous == 1
    assert stats.merged == 0
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (stub,)
            ).fetchone()
            is not None
        )


def test_stub_with_no_numbered_sibling_is_left_alone(db_url: str) -> None:
    """A genuine bound-morpheme-only stub (no own entry) is not a bug.

    Most etym_key='' references (foreign ancestor mentions, roots with
    no own Wiktionary page) never gain a numbered sibling at all --
    those are correct as-is, not something this backfill should touch.
    """
    with psycopg.connect(db_url) as conn:
        stub = _insert_lexeme(conn, headword="priHos", lang_code="ine-pro")
        conn.commit()

    stats = backfill_bound_morpheme_stubs.backfill(db_url, execute=True)

    assert stats.merged == 0
    assert stats.ambiguous == 0
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (stub,)
            ).fetchone()
            is not None
        )


def test_stub_with_its_own_senses_is_left_untouched(db_url: str) -> None:
    """A merge that would silently drop sense rows is skipped instead."""
    with psycopg.connect(db_url) as conn:
        _insert_lexeme(conn, headword="con", etymology_number="1")
        stub = _insert_lexeme(conn, headword="con")
        conn.execute(
            "INSERT INTO sense (lexeme_id, pos, gloss, source_ref) "
            "VALUES (%s, 'noun', 'a trick', 'w:0')",
            (stub,),
        )
        conn.commit()

    stats = backfill_bound_morpheme_stubs.backfill(db_url, execute=True)

    assert stats.merged == 0
    assert stats.ambiguous == 0
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (stub,)
            ).fetchone()
            is not None
        )


def test_dry_run_leaves_the_database_unchanged(db_url: str) -> None:
    """Without --execute, the transaction rolls back and nothing sticks."""
    with psycopg.connect(db_url) as conn:
        _insert_lexeme(conn, headword="con", etymology_number="1")
        _insert_lexeme(conn, headword="con")
        conn.commit()

    stats = backfill_bound_morpheme_stubs.backfill(db_url, execute=False)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert _lexeme_count(conn) == 2
