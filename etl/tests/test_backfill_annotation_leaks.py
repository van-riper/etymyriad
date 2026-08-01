"""DB-backed tests for the ETYM-102 inline-annotation-leak backfill.

`scripts/backfill_annotation_leaks.py` sits outside the `etymyriad`
package (see pyproject.toml's `scripts/*.py` lint carve-out), so it is
loaded here by file path rather than a normal import.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import psycopg
import pytest

if TYPE_CHECKING:
    from types import ModuleType

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "backfill_annotation_leaks.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "backfill_annotation_leaks", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill_annotation_leaks = _load_script()


@pytest.mark.parametrize(
    ("leaked", "correct"),
    [
        ("un-<id:reversive>", "un-"),
        ("-ing<id:gerund noun>", "-ing"),
        ("-gal<pos:gentilic suffix>", "-gal"),
        # a value containing its own "<...>" markup is still fine, as
        # long as the headword prefix and the outer block are clean.
        (
            (
                'weith<pos:soft mutation of <i class="Latn mention" '
                'lang="wlm">gweith</i> ("time, occasion")>'
            ),
            "weith",
        ),
    ],
)
def test_correct_headword_recognizes_a_leaked_annotation(
    leaked: str, correct: str
) -> None:
    """A bare word plus one trailing "<tag>" or "<tag:value>" block resolves."""
    assert backfill_annotation_leaks._correct_headword(leaked) == correct


@pytest.mark.parametrize(
    "leaked",
    [
        "<unc>",  # no headword text before the tag at all
        "etymology",  # no annotation to strip
        # raw HTML mention markup leaked in from an unrelated bug, not
        # Wiktextract's own annotation shape (real production rows):
        '<i class="Latn mention" lang="cy">hon</i> ("this")',
        'Proto-Slavic <i class="Latn mention" lang="sla-pro">*orky</i>',
        # two entries joined by a literal newline, also seen in prod:
        "gwen\ngwyn</i>>",
    ],
)
def test_correct_headword_rejects_anything_else(leaked: str) -> None:
    """Text that isn't a clean leaked annotation is never guessed at."""
    assert backfill_annotation_leaks._correct_headword(leaked) is None


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


def _headwords(conn: psycopg.Connection) -> set[str]:
    return {
        row[0] for row in conn.execute("SELECT headword FROM lexeme").fetchall()
    }


def _etymology_count(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM etymology").fetchone()
    assert row is not None
    return row[0]


def _lexeme_count(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM lexeme").fetchone()
    assert row is not None
    return row[0]


def test_merges_leaked_node_into_existing_real_node(db_url: str) -> None:
    """A leaked node with a real counterpart repoints edges, then is dropped."""
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="un-")
        leaked = _insert_lexeme(conn, headword="un-<id:reversive>")
        other = _insert_lexeme(conn, headword="reverse")
        _insert_edge(conn, src_id=leaked, dst_id=other, rel_type="affix")
        conn.commit()

    stats = backfill_annotation_leaks.backfill(db_url, execute=True)

    assert stats.merged == 1
    assert stats.renamed == stats.ambiguous == stats.unsafe == 0
    assert stats.unrecognized == 0
    with psycopg.connect(db_url) as conn:
        assert "un-<id:reversive>" not in _headwords(conn)
        edge = conn.execute(
            "SELECT src_id::text, dst_id::text FROM etymology"
        ).fetchone()
        assert edge == (real, other)
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (leaked,)
            ).fetchone()
            is None
        )


def test_merge_skips_edge_that_would_become_a_self_loop(db_url: str) -> None:
    """An edge directly between the leaked node and its real self is dropped.

    Repointing both ends onto the same target would otherwise violate
    the etymology_no_self_loop check.
    """
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="un-")
        leaked = _insert_lexeme(conn, headword="un-<id:reversive>")
        _insert_edge(conn, src_id=leaked, dst_id=real, rel_type="affix")
        conn.commit()

    stats = backfill_annotation_leaks.backfill(db_url, execute=True)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert _etymology_count(conn) == 0


def test_merge_drops_edge_colliding_with_an_existing_one(db_url: str) -> None:
    """A repoint duplicating an existing edge is skipped, not raised."""
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="un-")
        leaked = _insert_lexeme(conn, headword="un-<id:reversive>")
        other = _insert_lexeme(conn, headword="reverse")
        _insert_edge(conn, src_id=real, dst_id=other, rel_type="affix")
        _insert_edge(conn, src_id=leaked, dst_id=other, rel_type="affix")
        conn.commit()

    stats = backfill_annotation_leaks.backfill(db_url, execute=True)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert _etymology_count(conn) == 1


def test_renames_leaked_node_with_no_real_counterpart(db_url: str) -> None:
    """A leaked node with no real match is renamed in place, not deleted."""
    with psycopg.connect(db_url) as conn:
        leaked = _insert_lexeme(conn, headword="un-<id:reversive>")
        conn.commit()

    stats = backfill_annotation_leaks.backfill(db_url, execute=True)

    assert stats.renamed == 1
    assert stats.merged == stats.ambiguous == stats.unsafe == 0
    assert stats.unrecognized == 0
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT headword FROM lexeme WHERE id = %s", (leaked,)
        ).fetchone()
        assert row == ("un-",)


def test_ambiguous_match_is_left_untouched(db_url: str) -> None:
    """More than one real-node candidate is reported, not guessed at."""
    with psycopg.connect(db_url) as conn:
        _insert_lexeme(conn, headword="un-", etymology_number="1")
        _insert_lexeme(conn, headword="un-", etymology_number="2")
        leaked = _insert_lexeme(conn, headword="un-<id:reversive>")
        conn.commit()

    stats = backfill_annotation_leaks.backfill(db_url, execute=True)

    assert stats.ambiguous == 1
    assert stats.merged == stats.renamed == stats.unsafe == 0
    assert stats.unrecognized == 0
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT headword FROM lexeme WHERE id = %s", (leaked,)
        ).fetchone()
        assert row == ("un-<id:reversive>",)


def test_unrecognized_shape_is_left_untouched(db_url: str) -> None:
    """Raw HTML mention markup leaked from an unrelated bug is never renamed.

    A real production row (`wlm`, seen in a live dry run) had this
    exact shape and would have been renamed to an empty headword by a
    naive "split on the first <" -- corrupting a real node instead of
    fixing one.
    """
    headword = '<i class="Latn mention" lang="cy">hon</i> ("this")'
    with psycopg.connect(db_url) as conn:
        leaked = _insert_lexeme(conn, headword=headword)
        conn.commit()

    stats = backfill_annotation_leaks.backfill(db_url, execute=True)

    assert stats.unrecognized == 1
    assert stats.merged == stats.renamed == stats.ambiguous == stats.unsafe == 0
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT headword FROM lexeme WHERE id = %s", (leaked,)
        ).fetchone()
        assert row == (headword,)


def test_leaked_node_with_its_own_senses_is_left_untouched(db_url: str) -> None:
    """A merge that would silently drop sense rows is skipped instead."""
    with psycopg.connect(db_url) as conn:
        _insert_lexeme(conn, headword="un-")
        leaked = _insert_lexeme(conn, headword="un-<id:reversive>")
        conn.execute(
            "INSERT INTO sense (lexeme_id, pos, gloss, source_ref) "
            "VALUES (%s, 'prefix', 'not', 'w:0')",
            (leaked,),
        )
        conn.commit()

    stats = backfill_annotation_leaks.backfill(db_url, execute=True)

    assert stats.unsafe == 1
    assert stats.merged == stats.renamed == stats.ambiguous == 0
    assert stats.unrecognized == 0
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (leaked,)
            ).fetchone()
            is not None
        )


def test_dry_run_leaves_the_database_unchanged(db_url: str) -> None:
    """Without --execute, the transaction rolls back and nothing sticks."""
    with psycopg.connect(db_url) as conn:
        _insert_lexeme(conn, headword="un-")
        _insert_lexeme(conn, headword="un-<id:reversive>")
        conn.commit()

    stats = backfill_annotation_leaks.backfill(db_url, execute=False)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert "un-<id:reversive>" in _headwords(conn)
        assert _lexeme_count(conn) == 2
