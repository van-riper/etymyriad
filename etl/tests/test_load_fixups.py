"""Tests for post-merge fixups (split-stub merge, redlinks, degree)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import psycopg

from etymyriad.load import load_edges
from etymyriad.load._fixups import _fixup_and_index
from etymyriad.load._merge import _merge_staged_data
from etymyriad.load._schema import _TARGET_SCHEMA, _rebuild_schema
from etymyriad.load._staging import _stage_items
from etymyriad.model import EtymEdge, Lexeme, RelType, Sense

if TYPE_CHECKING:
    from collections.abc import Iterable

_SCHEMA_SQL_FILE = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

_ANCESTOR = Lexeme(
    lang_code="ine-pro",
    headword="leǵ-",
    is_reconstructed=True,
    source_ref="wiktionary:2026-06-01:ine-pro:leǵ-",
)


def _etymology(  # ruff: ignore[too-many-arguments] - test builder, one kwarg per Lexeme field
    *,
    gloss: str | None = None,
    pos: str | None = None,
    etymology_number: str | None = None,
    romanization: str | None = None,
    is_reconstructed: bool = False,
    is_redlink: bool = False,
    source_ref: str = "w:0",
) -> Lexeme:
    """Build an en "etymology" lexeme, wrapping pos/gloss into a Sense.

    Mirrors an entry's shape post-fix: pos/gloss live on a Sense, while
    lexeme identity is lang_code/headword/etymology_number.

    Returns:
        The built Lexeme.
    """
    senses = (
        (Sense(pos=pos, gloss=gloss, source_ref=source_ref),)
        if pos is not None or gloss is not None
        else ()
    )
    return Lexeme(
        lang_code="en",
        headword="etymology",
        etymology_number=etymology_number,
        romanization=romanization,
        is_reconstructed=is_reconstructed,
        is_redlink=is_redlink,
        source_ref=source_ref,
        senses=senses,
    )


def _edge(dst: Lexeme) -> EtymEdge:
    return EtymEdge(
        src=_ANCESTOR,
        dst=dst,
        rel_type=RelType.INHERITED,
        source_ref="wiktionary:2026-06-01:edge",
    )


def _run_merge_and_fixups(
    db_url: str, items: Iterable[EtymEdge | Lexeme]
) -> None:
    """Build `loading`, stage/merge `items`, then index and fix them up.

    Calls production's own post-merge sequence rather than restating it,
    so a reordering there can never drift away from what these tests
    exercise.
    """
    schema_sql = _SCHEMA_SQL_FILE.read_text(encoding="utf-8")
    with psycopg.connect(db_url, autocommit=True) as conn:
        _rebuild_schema(conn.cursor(), schema_sql)

    _, seen_languages = _stage_items(db_url, items)

    with psycopg.connect(db_url, autocommit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        _merge_staged_data(cursor, seen_languages)

    with psycopg.connect(db_url, autocommit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        _fixup_and_index(cursor)


def test_upsert_clears_redlink_for_headword_split_by_etymology_number(
    db_url: str,
) -> None:
    """A homograph split by etymology_number folds its redlink stub in.

    Real record: en "-er" splits into ten numbered entries (etymology_number
    "1".."10"); a template reference to "-er" has no way to say which
    number it means, so it resolves to an unnumbered stub whose etym_key
    ('') never matches any numbered entry's. is_redlink means "no entry
    anywhere in the dump for this headword", not "no entry at this exact
    etym_key", so a real entry under a different etymology_number must
    still resolve the unnumbered stub -- by merging it into that entry,
    not just clearing its flag while it stays a separate, disconnected
    row.
    """
    stub_edge = _edge(_etymology(is_redlink=True, source_ref="w:1"))
    real_edge = _edge(
        _etymology(etymology_number="1", is_redlink=False, source_ref="w:2")
    )

    # The second load is a full run's dataset, so it still contains the
    # edge that created the unnumbered stub, alongside the new numbered
    # entry -- otherwise the stub is legitimately stale and gets purged.
    load_edges(db_url, [stub_edge])
    load_edges(db_url, [stub_edge, real_edge])

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT etymology_number, is_redlink FROM lexeme "
            "WHERE headword = 'etymology'"
        ).fetchall()
        edge_dst_numbers = conn.execute(
            "SELECT l.etymology_number FROM etymology AS e "
            "JOIN lexeme AS l ON l.id = e.dst_id "
            "WHERE l.headword = 'etymology'"
        ).fetchall()

    assert rows == [("1", False)]
    assert edge_dst_numbers == [("1",)]


def test_merge_reassigns_ancestor_stub_edges_to_lowest_numbered_sibling(
    db_url: str,
) -> None:
    """A compound piece's ancestor stub resolves onto its real headword.

    Real record: "roofstone" -> "roof" via {{af}} builds an unnumbered
    "roof" stub, but en "roof" splits into etymology_number "1" and "2".
    Once both real sections load, the stub must fold onto one of them
    (the lowest-numbered, "1") instead of staying a disconnected leaf
    with no ancestors of its own.
    """
    descendant = Lexeme(
        lang_code="en", headword="roofstone", source_ref="w:descendant"
    )
    compound_edge = EtymEdge(
        src=_etymology(is_redlink=True, source_ref="w:stub"),
        dst=descendant,
        rel_type=RelType.AFFIX,
        source_ref="w:edge",
    )
    real_edges = [
        _edge(_etymology(etymology_number="2", pos="noun", source_ref="w:2")),
        _edge(_etymology(etymology_number="1", pos="verb", source_ref="w:3")),
    ]

    _run_merge_and_fixups(db_url, [compound_edge, *real_edges])

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        stub = conn.execute(
            "SELECT 1 FROM lexeme "
            "WHERE headword = 'etymology' AND etymology_number IS NULL"
        ).fetchone()
        ancestor_number = conn.execute(
            "SELECT l.etymology_number FROM etymology AS e "
            "JOIN lexeme AS l ON l.id = e.src_id "
            "JOIN lexeme AS d ON d.id = e.dst_id "
            "WHERE d.headword = 'roofstone'"
        ).fetchone()

    assert stub is None
    assert ancestor_number is not None
    assert ancestor_number[0] == "1"


def test_merge_skips_self_referencing_split_headword(db_url: str) -> None:
    """Doesn't fold a stub into itself when that would self-loop.

    Real record: a headword's etymology 2 section cross-references its
    own etymology 1 via an unnumbered self-citation (Wiktionary's own
    convention, e.g. {{der|pt|pt|matreira|pos=etymology 1}} on
    "matreira" itself). If that cited section also happens to be the
    lowest-numbered real sibling, folding the stub into it would make
    the entry its own ancestor -- the edge must stay exactly as parsed
    instead of collapsing into a self-loop.
    """
    self_citing_edge = EtymEdge(
        src=_etymology(is_redlink=True, source_ref="w:1"),
        dst=_etymology(etymology_number="1", pos="noun", source_ref="w:2"),
        rel_type=RelType.DERIVED,
        source_ref="w:edge",
    )

    load_edges(db_url, [self_citing_edge])

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT etymology_number FROM lexeme WHERE headword = 'etymology' "
            "ORDER BY etymology_number NULLS FIRST"
        ).fetchall()

    assert [row[0] for row in rows] == [None, "1"]


def test_load_computes_degree_from_etymology_edges(db_url: str) -> None:
    """Degree lands as total in+out etymology edges per lexeme.

    An edgeless lexeme (a lone entry with no ancestor-asserting
    template) gets degree 0, not skipped.
    """
    isolated = Lexeme(lang_code="en", headword="isolated", source_ref="w:0")

    load_edges(db_url, [_edge(_etymology(source_ref="w:1")), isolated])

    with psycopg.connect(db_url) as conn:
        degrees = dict(
            conn.execute("SELECT headword, degree FROM lexeme").fetchall()
        )

    assert degrees == {"leǵ-": 1, "etymology": 1, "isolated": 0}


def test_fixups_fold_split_stub_and_clear_its_redlink(
    db_url: str,
) -> None:
    """A homograph split by etymology_number folds its redlink stub in.

    Real record: en "-er" splits into ten numbered entries; a template
    reference to "-er" has no way to say which number it means, so it
    resolves to an unnumbered stub whose etym_key never matches any
    numbered entry's.
    """
    stub_edge = _edge(_etymology(is_redlink=True, source_ref="w:1"))
    real_edge = _edge(
        _etymology(etymology_number="1", is_redlink=False, source_ref="w:2")
    )

    _run_merge_and_fixups(db_url, [stub_edge, real_edge])

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        rows = conn.execute(
            "SELECT etymology_number, is_redlink FROM lexeme "
            "WHERE headword = 'etymology'"
        ).fetchall()

    assert rows == [("1", False)]


def test_fixups_skip_self_referencing_split_headword(
    db_url: str,
) -> None:
    """Doesn't fold a stub into itself when that would self-loop."""
    self_citing_edge = EtymEdge(
        src=_etymology(is_redlink=True, source_ref="w:1"),
        dst=_etymology(etymology_number="1", pos="noun", source_ref="w:2"),
        rel_type=RelType.DERIVED,
        source_ref="w:edge",
    )

    _run_merge_and_fixups(db_url, [self_citing_edge])

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        rows = conn.execute(
            "SELECT etymology_number FROM lexeme WHERE headword = 'etymology' "
            "ORDER BY etymology_number NULLS FIRST"
        ).fetchall()

    assert [row[0] for row in rows] == [None, "1"]


def test_recompute_degree_counts_in_and_out_edges(
    db_url: str,
) -> None:
    """Degree is total in+out etymology edges; an edgeless lexeme gets 0."""
    isolated = Lexeme(lang_code="en", headword="isolated", source_ref="w:0")

    _run_merge_and_fixups(
        db_url, [_edge(_etymology(source_ref="w:1")), isolated]
    )

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        degrees = dict(
            conn.execute("SELECT headword, degree FROM lexeme").fetchall()
        )

    assert degrees == {"leǵ-": 1, "etymology": 1, "isolated": 0}


def test_fixups_skip_duplicate_when_real_sibling_already_has_edge(
    db_url: str,
) -> None:
    """A stub's edge that would duplicate the real sibling's own edge.

    When the real sibling lexeme already owns an edge to the same
    descendant with the same relation type, the stub's equivalent edge
    is not inserted a second time.
    """
    descendant = Lexeme(
        lang_code="en", headword="roofstone", source_ref="w:descendant"
    )
    stub_edge = EtymEdge(
        src=_etymology(is_redlink=True, source_ref="w:stub"),
        dst=descendant,
        rel_type=RelType.AFFIX,
        source_ref="w:stub-edge",
    )
    real_sibling = _etymology(
        etymology_number="1", pos="noun", source_ref="w:real"
    )
    real_edge = EtymEdge(
        src=real_sibling,
        dst=descendant,
        rel_type=RelType.AFFIX,
        source_ref="w:real-edge",
    )

    _run_merge_and_fixups(db_url, [stub_edge, real_edge])

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        rows = conn.execute(
            "SELECT count(*) FROM etymology e "
            "JOIN lexeme src ON src.id = e.src_id "
            "JOIN lexeme dst ON dst.id = e.dst_id "
            "WHERE src.headword = 'etymology' "
            "AND dst.headword = 'roofstone'"
        ).fetchone()
        degree = conn.execute(
            "SELECT degree FROM lexeme WHERE headword = 'roofstone'"
        ).fetchone()

    assert rows == (1,)
    assert degree == (1,)


def test_fixup_and_index_recreates_all_five(db_url: str) -> None:
    """Every deferred index/constraint exists again afterwards.

    Including lexeme_degree_idx, which the split rebuild only creates
    after the degree recompute has filled the column it filters on.
    """
    _run_merge_and_fixups(db_url, [_edge(_etymology(source_ref="w:1"))])

    with psycopg.connect(db_url) as conn:
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'loading'"
            ).fetchall()
        }
        constraint = conn.execute(
            "SELECT conname FROM pg_constraint "
            "WHERE conname = 'etymology_unique_edge'"
        ).fetchone()

    assert {
        "lexeme_natural_key",
        "lexeme_headword_trgm",
        "lexeme_degree_idx",
        "sense_natural_key",
        "etymology_dst_idx",
    } <= indexes
    assert constraint == ("etymology_unique_edge",)
