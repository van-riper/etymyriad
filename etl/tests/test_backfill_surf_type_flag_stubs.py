"""DB-backed tests for the {{surf}} edge reconciliation backfill.

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

_DUMP_DATE = "2026-06-01"


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


def _entry(
    lang_code: str, word: str, surf_args: dict[str, str]
) -> dict[str, object]:
    return {
        "word": word,
        "lang_code": lang_code,
        "etymology_templates": [{"name": "surf", "args": surf_args}],
    }


def _source_ref(lang_code: str, word: str, index: int = 0) -> str:
    return (
        f"wiktionary:{_DUMP_DATE}:{lang_code}:{word}"
        f"#etymology_templates:{index}:surf"
    )


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
            source_ref or f"wiktionary:{_DUMP_DATE}:{lang_code}:{headword}",
        ),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_edge(
    conn: psycopg.Connection,
    *,
    src_id: str,
    dst_id: str,
    source_ref: str,
    piece_order: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO etymology (src_id, dst_id, rel_type, source_ref, "
        "piece_order) VALUES (%s, %s, 'surface_analysis', %s, %s)",
        (src_id, dst_id, source_ref, piece_order),
    )


def _lexeme_row(
    conn: psycopg.Connection, lexeme_id: str
) -> tuple[str, str] | None:
    row = conn.execute(
        "SELECT lang_code, headword FROM lexeme WHERE id = %s", (lexeme_id,)
    ).fetchone()
    return (row[0], row[1]) if row else None


def _edges_for(
    conn: psycopg.Connection, source_ref: str
) -> set[tuple[str, str, int | None]]:
    rows = conn.execute(
        "SELECT src.lang_code, src.headword, e.piece_order "
        "FROM etymology e JOIN lexeme src ON src.id = e.src_id "
        "WHERE e.source_ref = %s",
        (source_ref,),
    ).fetchall()
    return {(row[0], row[1], row[2]) for row in rows}


def test_phantom_leaked_language_piece_is_deleted(db_url: str) -> None:
    """A phantom piece matching no correct term is deleted outright.

    Real shape: {{surf|+clipping|pl|kilogram}} on pl "kilo". The old
    parser leaked "pl" in as a bogus extra piece alongside the real
    "kilogram" one.
    """
    source_ref = _source_ref("pl", "kilo")
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, lang_code="pl", headword="kilo")
        phantom = _insert_lexeme(conn, lang_code="pl", headword="pl")
        real = _insert_lexeme(conn, lang_code="pl", headword="kilogram")
        _insert_edge(
            conn,
            src_id=phantom,
            dst_id=dst,
            source_ref=source_ref,
            piece_order=1,
        )
        _insert_edge(
            conn, src_id=real, dst_id=dst, source_ref=source_ref, piece_order=2
        )
        conn.commit()

    entries = [
        _entry("pl", "kilo", {"1": "+clipping", "2": "pl", "3": "kilogram"})
    ]
    stats = backfill_surf_type_flag_stubs.backfill(
        db_url, entries, _DUMP_DATE, execute=True
    )

    assert stats.deleted == 1
    assert stats.repaired == 1
    with psycopg.connect(db_url) as conn:
        assert _edges_for(conn, source_ref) == {("pl", "kilogram", 1)}


def test_repairs_null_piece_order(db_url: str) -> None:
    """An edge already on the right lexeme still gets its piece_order fixed."""
    source_ref = _source_ref("en", "community")
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, lang_code="en", headword="community")
        real = _insert_lexeme(conn, lang_code="en", headword="commune")
        _insert_edge(
            conn,
            src_id=real,
            dst_id=dst,
            source_ref=source_ref,
            piece_order=None,
        )
        conn.commit()

    entries = [
        _entry("en", "community", {"1": "+suf", "2": "en", "3": "commune"})
    ]
    stats = backfill_surf_type_flag_stubs.backfill(
        db_url, entries, _DUMP_DATE, execute=True
    )

    assert stats.repaired == 1
    with psycopg.connect(db_url) as conn:
        assert _edges_for(conn, source_ref) == {("en", "commune", 1)}


def test_repoints_a_still_flagged_stub_onto_its_real_language(
    db_url: str,
) -> None:
    """An edge still on a "+flag" stub is repointed onto the real one."""
    source_ref = _source_ref("en", "community")
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, lang_code="en", headword="community")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="ity")
        _insert_edge(
            conn, src_id=stub, dst_id=dst, source_ref=source_ref, piece_order=1
        )
        conn.commit()

    entries = [_entry("en", "community", {"1": "+suf", "2": "en", "3": "ity"})]
    stats = backfill_surf_type_flag_stubs.backfill(
        db_url, entries, _DUMP_DATE, execute=True
    )

    assert stats.repaired == 1
    with psycopg.connect(db_url) as conn:
        assert _edges_for(conn, source_ref) == {("en", "ity", 1)}


def test_orphaned_stub_is_deleted_after_reconciliation(db_url: str) -> None:
    """A stub left with no edges and no senses after repair is deleted."""
    source_ref = _source_ref("en", "community")
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, lang_code="en", headword="community")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="ity")
        _insert_edge(
            conn, src_id=stub, dst_id=dst, source_ref=source_ref, piece_order=1
        )
        conn.commit()

    entries = [_entry("en", "community", {"1": "+suf", "2": "en", "3": "ity"})]
    stats = backfill_surf_type_flag_stubs.backfill(
        db_url, entries, _DUMP_DATE, execute=True
    )

    assert stats.orphans_deleted == 1
    with psycopg.connect(db_url) as conn:
        assert _lexeme_row(conn, stub) is None


def test_inserts_a_correct_piece_missing_its_edge(db_url: str) -> None:
    """A correct piece with no current edge at all gets inserted."""
    source_ref = _source_ref("en", "abduction")
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, lang_code="en", headword="abduction")
        real = _insert_lexeme(conn, lang_code="en", headword="abduct")
        _insert_edge(
            conn, src_id=real, dst_id=dst, source_ref=source_ref, piece_order=1
        )
        conn.commit()

    entries = [
        _entry(
            "en",
            "abduction",
            {"1": "+suf", "2": "en", "3": "abduct", "4": "-ion"},
        )
    ]
    stats = backfill_surf_type_flag_stubs.backfill(
        db_url, entries, _DUMP_DATE, execute=True
    )

    assert stats.inserted == 1
    with psycopg.connect(db_url) as conn:
        assert _edges_for(conn, source_ref) == {
            ("en", "abduct", 1),
            ("en", "-ion", 2),
        }


def test_missing_piece_shared_with_a_sibling_template_is_skipped(
    db_url: str,
) -> None:
    """A missing piece already claimed by a sibling template is left alone.

    Real shape: en "rosier" derives "rosy" as piece 1 via two separate
    {{surf}} calls (one for "-ier", one for "-er"). Only one edge can
    exist for (rosy, rosier, surface_analysis) under
    etymology_unique_edge, so the second template's own "rosy" piece
    has nowhere to land -- inserting or overwriting it would just
    mislabel the first template's surviving edge, and retrying every
    run would never converge.
    """
    source_ref_a = _source_ref("en", "rosier", index=0)
    source_ref_b = _source_ref("en", "rosier", index=1)
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, lang_code="en", headword="rosier")
        rosy = _insert_lexeme(conn, lang_code="en", headword="rosy")
        ier = _insert_lexeme(conn, lang_code="en", headword="-ier")
        er = _insert_lexeme(conn, lang_code="en", headword="-er")
        _insert_edge(
            conn,
            src_id=rosy,
            dst_id=dst,
            source_ref=source_ref_a,
            piece_order=1,
        )
        _insert_edge(
            conn, src_id=ier, dst_id=dst, source_ref=source_ref_a, piece_order=2
        )
        _insert_edge(
            conn, src_id=er, dst_id=dst, source_ref=source_ref_b, piece_order=2
        )
        conn.commit()

    entries = [
        {
            "word": "rosier",
            "lang_code": "en",
            "etymology_templates": [
                {"name": "surf", "args": {"1": "en", "2": "rosy", "3": "-ier"}},
                {"name": "surf", "args": {"1": "en", "2": "rosy", "3": "-er"}},
            ],
        }
    ]

    stats = backfill_surf_type_flag_stubs.backfill(
        db_url, entries, _DUMP_DATE, execute=True
    )
    assert stats.inserted == 0
    with psycopg.connect(db_url) as conn:
        assert _edges_for(conn, source_ref_b) == {("en", "-er", 2)}

    stats_again = backfill_surf_type_flag_stubs.backfill(
        db_url, entries, _DUMP_DATE, execute=True
    )
    assert stats_again == backfill_surf_type_flag_stubs.Stats(orphans_deleted=0)


def test_unresolved_source_ref_is_left_untouched(db_url: str) -> None:
    """An edge whose source_ref isn't in the dump is skipped, not guessed."""
    source_ref = _source_ref("en", "ghost")
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, lang_code="en", headword="ghost")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="ity")
        _insert_edge(
            conn, src_id=stub, dst_id=dst, source_ref=source_ref, piece_order=1
        )
        conn.commit()

    stats = backfill_surf_type_flag_stubs.backfill(
        db_url, [], _DUMP_DATE, execute=True
    )

    assert stats.unresolved == 1
    assert stats.repaired == stats.deleted == stats.inserted == 0
    with psycopg.connect(db_url) as conn:
        assert _edges_for(conn, source_ref) == {("+suf", "ity", 1)}


def test_zero_piece_template_deletes_its_edge_not_unresolved(
    db_url: str,
) -> None:
    """A template that correctly yields no pieces still counts as found.

    Real shape: {{surf|+lit|good day}} on csb "dobri dzéń" -- the dump
    entry exists and the template is real, but the fixed parser
    produces zero pieces for it. A source_ref like this must not be
    confused with one absent from the dump entirely: the edge the old
    parser wrongly created for it is a phantom to delete, not a case
    to leave untouched as unresolved.
    """
    source_ref = _source_ref("csb", "dobri dzen")
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, lang_code="csb", headword="dobri dzen")
        stub = _insert_lexeme(conn, lang_code="+lit", headword="good day")
        _insert_edge(
            conn, src_id=stub, dst_id=dst, source_ref=source_ref, piece_order=1
        )
        conn.commit()

    entries = [_entry("csb", "dobri dzen", {"1": "+lit", "2": "good day"})]
    stats = backfill_surf_type_flag_stubs.backfill(
        db_url, entries, _DUMP_DATE, execute=True
    )

    assert stats.deleted == 1
    assert stats.unresolved == 0
    with psycopg.connect(db_url) as conn:
        assert _edges_for(conn, source_ref) == set()


def test_dry_run_makes_no_changes(db_url: str) -> None:
    """Without --execute (execute=False), the transaction rolls back."""
    source_ref = _source_ref("en", "community")
    with psycopg.connect(db_url) as conn:
        dst = _insert_lexeme(conn, lang_code="en", headword="community")
        stub = _insert_lexeme(conn, lang_code="+suf", headword="ity")
        _insert_edge(
            conn, src_id=stub, dst_id=dst, source_ref=source_ref, piece_order=1
        )
        conn.commit()

    entries = [_entry("en", "community", {"1": "+suf", "2": "en", "3": "ity"})]
    stats = backfill_surf_type_flag_stubs.backfill(
        db_url, entries, _DUMP_DATE, execute=False
    )

    assert stats.repaired == 1
    with psycopg.connect(db_url) as conn:
        assert _edges_for(conn, source_ref) == {("+suf", "ity", 1)}
