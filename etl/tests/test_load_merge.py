"""Tests for resolving staged natural keys into real graph rows."""

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


def _run_merge(db_url: str, items: Iterable[EtymEdge | Lexeme]) -> None:
    """Build `loading`, stage `items`, and merge them.

    Everything `load_edges` does short of fixups, indexing, and the swap.
    """
    schema_sql = _SCHEMA_SQL_FILE.read_text(encoding="utf-8")
    with psycopg.connect(db_url, autocommit=True) as conn:
        _rebuild_schema(conn.cursor(), schema_sql)

    _, seen_languages = _stage_items(db_url, items)

    with psycopg.connect(db_url, autocommit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        _merge_staged_data(cursor, seen_languages)


def test_sense_upsert_fills_source_ref_from_later_load(db_url: str) -> None:
    """A sense's source_ref updates to the latest load (latest-wins citation).

    Mirrors the lexeme upsert's own latest-wins convention: the natural key
    (lexeme_id, pos_key, gloss_key) stays the same across both loads, so the
    second load updates the existing sense row's source_ref rather than
    inserting a second one.
    """
    load_edges(db_url, [_edge(_etymology(pos="noun", source_ref="w:1"))])
    load_edges(db_url, [_edge(_etymology(pos="noun", source_ref="w:2"))])

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT source_ref FROM sense WHERE pos = 'noun'"
        ).fetchall()

    assert [row[0] for row in rows] == ["w:2"]


def test_upsert_fills_romanization_from_later_load(db_url: str) -> None:
    """A null romanization loaded first is filled by a later load."""
    load_edges(db_url, [_edge(_etymology(romanization=None, source_ref="w:1"))])
    load_edges(
        db_url, [_edge(_etymology(romanization="etymology", source_ref="w:2"))]
    )

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT romanization FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()

    assert row is not None
    assert row[0] == "etymology"


def test_load_backfills_name_for_preexisting_placeholder_language(
    db_url: str,
) -> None:
    """A language row seeded with name = code gets the real name on load.

    `ON CONFLICT (code) DO NOTHING` meant a language row inserted before
    its name mapping existed (or before Wiktionary had named it) was
    upserted once, then locked in with the placeholder forever.
    """
    with psycopg.connect(db_url) as conn:
        conn.execute(
            "INSERT INTO language (code, name, lang_family, is_proto) "
            "VALUES ('en', 'en', NULL, FALSE)"
        )
        conn.commit()

    load_edges(db_url, [_edge(_etymology(source_ref="w:1"))])

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT name, lang_family FROM language WHERE code = 'en'"
        ).fetchone()

    assert row is not None
    assert row[0] == "English"
    assert row[1] == "Germanic"


def test_upsert_latches_reconstructed_from_later_load(db_url: str) -> None:
    """is_reconstructed latches true even if a plain load came first."""
    load_edges(
        db_url, [_edge(_etymology(is_reconstructed=False, source_ref="w:1"))]
    )
    load_edges(
        db_url, [_edge(_etymology(is_reconstructed=True, source_ref="w:2"))]
    )

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT is_reconstructed FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()

    assert row is not None
    assert row[0] is True


def test_upsert_clears_redlink_once_a_real_entry_loads(db_url: str) -> None:
    """is_redlink AND-latches false, the opposite of is_reconstructed's OR.

    A referenced-only load defaults to a redlink; once the ancestor's own
    entry loads (in this run or a later one), the flag clears permanently
    regardless of load order.
    """
    load_edges(db_url, [_edge(_etymology(is_redlink=True, source_ref="w:1"))])
    load_edges(db_url, [_edge(_etymology(is_redlink=False, source_ref="w:2"))])

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT is_redlink FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()

    assert row is not None
    assert row[0] is False


def test_upsert_merges_same_etymology_number_into_two_senses(
    db_url: str,
) -> None:
    """Entries sharing etymology_number merge into one lexeme, many senses.

    Real record: en "reverse" adj/adv/noun all carry etymology_number "1"
    (one shared derivation) but distinct pos/gloss -- they must load as
    one lexeme row with two sense rows attached, not three separate
    same-labeled lexemes.
    """
    edges = [
        _edge(
            _etymology(
                etymology_number="1",
                pos="adj",
                gloss="Opposite, contrary; going in the opposite direction.",
                source_ref="w:1",
            )
        ),
        _edge(
            _etymology(
                etymology_number="1",
                pos="noun",
                gloss="The opposite of something.",
                source_ref="w:2",
            )
        ),
    ]

    load_edges(db_url, edges)

    with psycopg.connect(db_url) as conn:
        lexemes = conn.execute(
            "SELECT id FROM lexeme WHERE headword = 'etymology'"
        ).fetchall()
        assert len(lexemes) == 1
        senses = conn.execute(
            "SELECT pos FROM sense WHERE lexeme_id = %s ORDER BY pos",
            (lexemes[0][0],),
        ).fetchall()

    assert [row[0] for row in senses] == ["adj", "noun"]


def test_upsert_keeps_distinct_etymology_numbers_as_separate_lexemes(
    db_url: str,
) -> None:
    """Distinct etymology_numbers are genuinely separate derivations.

    Real record: en "reverse" verb carries etymology_number "2", a
    distinct derivation from the adj/adv/noun's "1" -- these must load as
    two separate lexeme rows, not merge.
    """
    edges = [
        _edge(_etymology(etymology_number="1", pos="adj", source_ref="w:1")),
        _edge(_etymology(etymology_number="2", pos="verb", source_ref="w:2")),
    ]

    load_edges(db_url, edges)

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT etymology_number FROM lexeme WHERE headword = 'etymology' "
            "ORDER BY etymology_number"
        ).fetchall()

    assert [row[0] for row in rows] == ["1", "2"]


def test_sense_upsert_is_idempotent(db_url: str) -> None:
    """Loading the exact same edge twice creates no duplicate sense row."""
    edge = _edge(_etymology(pos="noun", gloss="H2O", source_ref="w:1"))

    load_edges(db_url, [edge])
    load_edges(db_url, [edge])

    with psycopg.connect(db_url) as conn:
        row = conn.execute("SELECT count(*) FROM sense").fetchone()

    assert row is not None
    assert row[0] == 1


def test_load_persists_piece_order(db_url: str) -> None:
    """An edge's piece_order lands on the etymology row unchanged."""
    prefix = Lexeme(lang_code="en", headword="un-", source_ref="w:a")
    edge = EtymEdge(
        src=prefix,
        dst=_etymology(source_ref="w:1"),
        rel_type=RelType.AFFIX,
        source_ref="w:e",
        piece_order=1,
    )

    load_edges(db_url, [edge])

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT piece_order FROM etymology e "
            "JOIN lexeme l ON l.id = e.src_id WHERE l.headword = 'un-'"
        ).fetchone()

    assert row is not None
    assert row[0] == 1


def test_load_backfills_piece_order_on_later_load(db_url: str) -> None:
    """A later load's piece_order overwrites an already-loaded edge's.

    Lets a schema-evolution backfill populate piece_order on edges
    loaded before the column existed, by simply re-running the
    ETL: same edge, same (src_id, dst_id, rel_type) key, newly-computed
    piece_order.
    """
    prefix = Lexeme(lang_code="en", headword="un-", source_ref="w:a")
    dst = _etymology(source_ref="w:1")
    load_edges(
        db_url,
        [
            EtymEdge(
                src=prefix,
                dst=dst,
                rel_type=RelType.AFFIX,
                source_ref="w:e",
                piece_order=None,
            )
        ],
    )
    load_edges(
        db_url,
        [
            EtymEdge(
                src=prefix,
                dst=dst,
                rel_type=RelType.AFFIX,
                source_ref="w:e",
                piece_order=1,
            )
        ],
    )

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT piece_order FROM etymology e "
            "JOIN lexeme l ON l.id = e.src_id WHERE l.headword = 'un-'"
        ).fetchone()

    assert row is not None
    assert row[0] == 1


def test_merge_or_latches_is_reconstructed_across_occurrences(
    db_url: str,
) -> None:
    """A lexeme reconstructed in any occurrence stays reconstructed."""
    edges = [
        _edge(_etymology(is_reconstructed=False, source_ref="w:1")),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:2"),
            dst=_etymology(is_reconstructed=True, source_ref="w:1"),
            rel_type=RelType.INHERITED,
            source_ref="w:2",
        ),
    ]

    _run_merge(db_url, edges)

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        row = conn.execute(
            "SELECT is_reconstructed FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()

    assert row == (True,)


def test_merge_and_latches_is_redlink_across_occurrences(
    db_url: str,
) -> None:
    """A lexeme with any real (non-redlink) occurrence isn't a redlink."""
    edges = [
        _edge(_etymology(is_redlink=True, source_ref="w:1")),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:2"),
            dst=_etymology(is_redlink=False, source_ref="w:1"),
            rel_type=RelType.INHERITED,
            source_ref="w:2",
        ),
    ]

    _run_merge(db_url, edges)

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        row = conn.execute(
            "SELECT is_redlink FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()

    assert row == (False,)


def test_merge_dedupes_repeated_shared_endpoint_to_one_lexeme_row(
    db_url: str,
) -> None:
    """A common ancestor referenced by many edges collapses to one row."""
    shared = _etymology(source_ref="w:shared")
    edges = [_edge(shared) for _ in range(5)]

    _run_merge(db_url, edges)

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        row = conn.execute(
            "SELECT count(*) FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()

    assert row == (1,)


def test_merge_treats_an_empty_etymology_number_as_absent(
    db_url: str,
) -> None:
    """An empty-string etymology_number is the same row as a null one.

    The natural-key index keys on etym_key, which COALESCEs a null
    etymology_number to ''. Grouping the merge on the raw column instead
    would emit two rows for one key, and the index rebuild that follows
    would then reject them as duplicates and fail the whole reload.
    """
    edges = [
        _edge(_etymology(etymology_number="", source_ref="w:1")),
        _edge(_etymology(etymology_number=None, source_ref="w:2")),
    ]

    _run_merge(db_url, edges)
    with psycopg.connect(db_url, autocommit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        _fixup_and_index(cursor)

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        rows = conn.execute(
            "SELECT etymology_number FROM lexeme WHERE headword = 'etymology'"
        ).fetchall()

    assert rows == [(None,)]


def test_merge_prefers_a_non_null_romanization_over_a_null_one(
    db_url: str,
) -> None:
    """max() picks a real romanization/source_ref, never a null.

    Postgres' max() skips nulls, so one occurrence carrying a
    romanization wins over another that leaves it out, whichever order
    the two land in staging.
    """
    edges = [
        _edge(_etymology(romanization=None, source_ref="w:1")),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:2"),
            dst=_etymology(romanization="etymology", source_ref="w:2"),
            rel_type=RelType.INHERITED,
            source_ref="w:2",
        ),
    ]

    _run_merge(db_url, edges)

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        row = conn.execute(
            "SELECT romanization, source_ref FROM lexeme "
            "WHERE headword = 'etymology'"
        ).fetchone()

    assert row == ("etymology", "w:2")


def test_merge_dedupes_senses_and_resolves_edges_by_natural_key(
    db_url: str,
) -> None:
    """Senses dedupe exactly; edges resolve src/dst to the merged rows."""
    edges = [
        _edge(_etymology(etymology_number="1", pos="adj", source_ref="w:1")),
        _edge(_etymology(etymology_number="1", pos="noun", source_ref="w:2")),
    ]

    _run_merge(db_url, edges)

    with psycopg.connect(db_url) as conn:
        conn.execute(f"SET search_path TO {_TARGET_SCHEMA}")
        senses = conn.execute(
            "SELECT pos FROM sense s JOIN lexeme l ON l.id = s.lexeme_id "
            "WHERE l.headword = 'etymology' ORDER BY pos"
        ).fetchall()
        edge_count = conn.execute("SELECT count(*) FROM etymology").fetchone()

    assert senses == [("adj",), ("noun",)]
    assert edge_count == (1,)
