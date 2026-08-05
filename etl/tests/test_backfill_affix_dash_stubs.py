"""DB-backed tests for the affix-dash-stub backfill.

`scripts/backfill_affix_dash_stubs.py` sits outside the `etymyriad`
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
    / "backfill_affix_dash_stubs.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "backfill_affix_dash_stubs", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill_affix_dash_stubs = _load_script()


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


def _lexeme_count(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM lexeme").fetchone()
    assert row is not None
    return row[0]


def test_merges_bare_stub_into_its_leading_dash_sibling(db_url: str) -> None:
    """A bare-spelling stub merges into its leading-dashed sibling.

    Real record: en "ic" the bound morpheme, referenced by other
    entries' {{suf}}/{{suffix}} templates as a bare arg, collapses onto
    a senseless etym_key='' stub distinct from en "-ic"'s own numbered
    dictionary entry.
    """
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(conn, headword="-ic", etymology_number="1")
        stub = _insert_lexeme(conn, headword="ic")
        other = _insert_lexeme(conn, headword="linguistic")
        _insert_edge(conn, src_id=stub, dst_id=other, rel_type="affix")
        conn.commit()

    stats = backfill_affix_dash_stubs.backfill(db_url, execute=True)

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


def test_merges_bare_stub_into_its_trailing_dash_sibling(db_url: str) -> None:
    """A bare-spelling stub merges into its trailing-dashed sibling.

    Real record: it "tri" the bound morpheme, referenced by
    {{prefix}} as a bare arg, collapses onto a stub distinct from it
    "tri-"'s own numbered dictionary entry.
    """
    with psycopg.connect(
        db_url,
    ) as conn:
        real = _insert_lexeme(
            conn, lang_code="it", headword="tri-", etymology_number="1"
        )
        stub = _insert_lexeme(conn, lang_code="it", headword="tri")
        conn.commit()

    stats = backfill_affix_dash_stubs.backfill(db_url, execute=True)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (real,)
            ).fetchone()
            is not None
        )
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (stub,)
            ).fetchone()
            is None
        )


def test_merges_bare_stub_into_its_infix_dash_sibling(db_url: str) -> None:
    """A bare-spelling stub merges into a both-sides-dashed sibling.

    Real record: tl "um" the bound morpheme, referenced by {{infix}}
    as a bare arg, collapses onto a stub distinct from tl "-um-"'s own
    numbered dictionary entry.
    """
    with psycopg.connect(db_url) as conn:
        real = _insert_lexeme(
            conn, lang_code="tl", headword="-um-", etymology_number="1"
        )
        stub = _insert_lexeme(conn, lang_code="tl", headword="um")
        conn.commit()

    stats = backfill_affix_dash_stubs.backfill(db_url, execute=True)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (real,)
            ).fetchone()
            is not None
        )
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (stub,)
            ).fetchone()
            is None
        )


def test_already_dashed_stub_is_left_alone(db_url: str) -> None:
    """A stub whose headword already carries a dash is out of scope.

    This backfill only targets the bare-spelling bug (ETYM-104); a
    stub already spelled with its dash is either correct as-is or a
    distinct issue (ETYM-96), not this one.
    """
    with psycopg.connect(db_url) as conn:
        stub = _insert_lexeme(conn, headword="-ic")
        conn.commit()

    stats = backfill_affix_dash_stubs.backfill(db_url, execute=True)

    assert stats.merged == 0
    assert stats.ambiguous == 0
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (stub,)
            ).fetchone()
            is not None
        )


def test_ambiguous_match_across_variants_is_left_untouched(
    db_url: str,
) -> None:
    """A stub matching more than one hyphenated sibling is reported.

    A bare headword could in principle carry either a leading or
    trailing dash; if both numbered siblings exist, the template gives
    no way to tell which one the stub means.
    """
    with psycopg.connect(db_url) as conn:
        _insert_lexeme(conn, headword="-ist", etymology_number="1")
        _insert_lexeme(conn, headword="ist-", etymology_number="1")
        stub = _insert_lexeme(conn, headword="ist")
        conn.commit()

    stats = backfill_affix_dash_stubs.backfill(db_url, execute=True)

    assert stats.ambiguous == 1
    assert stats.merged == 0
    with psycopg.connect(db_url) as conn:
        assert (
            conn.execute(
                "SELECT 1 FROM lexeme WHERE id = %s", (stub,)
            ).fetchone()
            is not None
        )


def test_stub_with_no_hyphenated_sibling_is_left_alone(db_url: str) -> None:
    """A bare headword with no dashed counterpart at all is not a bug.

    Most etym_key='' references never gain a hyphenated numbered
    sibling -- those are correct as-is, not something this backfill
    should touch.
    """
    with psycopg.connect(db_url) as conn:
        stub = _insert_lexeme(conn, headword="anti")
        conn.commit()

    stats = backfill_affix_dash_stubs.backfill(db_url, execute=True)

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
        _insert_lexeme(conn, headword="-ic", etymology_number="1")
        stub = _insert_lexeme(conn, headword="ic")
        conn.execute(
            "INSERT INTO sense (lexeme_id, pos, gloss, source_ref) "
            "VALUES (%s, 'suffix', 'a trick', 'w:0')",
            (stub,),
        )
        conn.commit()

    stats = backfill_affix_dash_stubs.backfill(db_url, execute=True)

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
        _insert_lexeme(conn, headword="-ic", etymology_number="1")
        _insert_lexeme(conn, headword="ic")
        conn.commit()

    stats = backfill_affix_dash_stubs.backfill(db_url, execute=False)

    assert stats.merged == 1
    with psycopg.connect(db_url) as conn:
        assert _lexeme_count(conn) == 2
