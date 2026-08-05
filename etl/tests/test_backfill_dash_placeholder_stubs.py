"""DB-backed tests for the ETYM-105 dash-placeholder-stub backfill.

`scripts/backfill_dash_placeholder_stubs.py` sits outside the
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
    / "backfill_dash_placeholder_stubs.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "backfill_dash_placeholder_stubs", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill_dash_placeholder_stubs = _load_script()


def _insert_lexeme(
    conn: psycopg.Connection, *, lang_code: str = "en", headword: str
) -> str:
    conn.execute(
        "INSERT INTO language (code, name) VALUES (%s, %s) "
        "ON CONFLICT (code) DO NOTHING",
        (lang_code, lang_code),
    )
    row = conn.execute(
        "INSERT INTO lexeme (lang_code, headword, source_ref) "
        "VALUES (%s, %s, 'w:0') RETURNING id::text",
        (lang_code, headword),
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


def _lexeme_count(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM lexeme").fetchone()
    assert row is not None
    return row[0]


def _etymology_count(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM etymology").fetchone()
    assert row is not None
    return row[0]


def test_deletes_dash_placeholder_lexeme_and_its_edges(db_url: str) -> None:
    """A "-" placeholder node and every edge pointing into it are dropped.

    Real record: cmn-pinyin's "-" node has 1,715 edges pointing into it
    (borrowed + derived), none with an actual attested term -- there is
    no real target to repoint onto, so these are dropped outright,
    unlike ETYM-96/104's stub merges.
    """
    with psycopg.connect(db_url) as conn:
        placeholder = _insert_lexeme(conn, lang_code="cmn-pinyin", headword="-")
        real = _insert_lexeme(conn, lang_code="en", headword="example")
        _insert_edge(conn, src_id=placeholder, dst_id=real, rel_type="borrowed")
        conn.commit()

    stats = backfill_dash_placeholder_stubs.backfill(db_url, execute=True)

    assert stats.deleted == 1
    assert stats.unsafe == 0
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (placeholder,)
            ).fetchone()
            is None
        )
        assert _etymology_count(conn) == 0
        assert _lexeme_count(conn) == 1


def test_a_dash_headword_with_its_own_senses_is_left_untouched(
    db_url: str,
) -> None:
    """A genuine dictionary entry literally headworded "-" is not deleted.

    A bogus placeholder node never carries senses of its own (see
    `_referenced_lexeme` in normalize.py); one that does is a real
    entry for the hyphen character itself, not the parser bug's stub.
    """
    with psycopg.connect(db_url) as conn:
        dash_entry = _insert_lexeme(conn, lang_code="en", headword="-")
        conn.execute(
            "INSERT INTO sense (lexeme_id, pos, gloss, source_ref) "
            "VALUES (%s, 'punct', 'hyphen', 'w:0')",
            (dash_entry,),
        )
        conn.commit()

    stats = backfill_dash_placeholder_stubs.backfill(db_url, execute=True)

    assert stats.deleted == 0
    assert stats.unsafe == 1
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (dash_entry,)
            ).fetchone()
            is not None
        )


def test_dry_run_leaves_the_database_unchanged(db_url: str) -> None:
    """Without --execute, the transaction rolls back and nothing sticks."""
    with psycopg.connect(db_url) as conn:
        _insert_lexeme(conn, lang_code="cmn-pinyin", headword="-")
        conn.commit()

    stats = backfill_dash_placeholder_stubs.backfill(db_url, execute=False)

    assert stats.deleted == 1
    with psycopg.connect(db_url) as conn:
        assert _lexeme_count(conn) == 1
