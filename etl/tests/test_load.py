"""DB-backed tests for the loader's upsert behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg

from etymyriad.load import _ensure_languages, load_edges
from etymyriad.model import EtymEdge, Lexeme, RelType, Sense

if TYPE_CHECKING:
    from collections.abc import Iterable

_ANCESTOR = Lexeme(
    lang_code="ine-pro",
    headword="wódr̥",
    is_reconstructed=True,
    source_ref="wiktionary:2026-06-01:ine-pro:wódr̥",
)


def _water(  # noqa: PLR0913 - test builder, one kwarg per Lexeme field
    *,
    gloss: str | None = None,
    pos: str | None = None,
    etymology_number: str | None = None,
    romanization: str | None = None,
    is_reconstructed: bool = False,
    source_ref: str = "w:0",
) -> Lexeme:
    """Build an en "water" lexeme, wrapping pos/gloss into a Sense.

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
        headword="water",
        etymology_number=etymology_number,
        romanization=romanization,
        is_reconstructed=is_reconstructed,
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


def test_sense_upsert_fills_source_ref_from_later_load(db_url: str) -> None:
    """A sense's source_ref updates to the latest load (latest-wins citation).

    Mirrors the lexeme upsert's own latest-wins convention: the natural key
    (lexeme_id, pos_key, gloss_key) stays the same across both loads, so the
    second load updates the existing sense row's source_ref rather than
    inserting a second one.
    """
    load_edges(db_url, [_edge(_water(pos="noun", source_ref="w:1"))])
    load_edges(db_url, [_edge(_water(pos="noun", source_ref="w:2"))])

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT source_ref FROM sense WHERE pos = 'noun'"
        ).fetchall()

    assert [row[0] for row in rows] == ["w:2"]


def test_upsert_fills_romanization_from_later_load(db_url: str) -> None:
    """A null romanization loaded first is filled by a later load."""
    load_edges(db_url, [_edge(_water(romanization=None, source_ref="w:1"))])
    load_edges(db_url, [_edge(_water(romanization="water", source_ref="w:2"))])

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT romanization FROM lexeme WHERE headword = 'water'"
        ).fetchone()

    assert row is not None
    assert row[0] == "water"


def test_upsert_latches_reconstructed_from_later_load(db_url: str) -> None:
    """is_reconstructed latches true even if a plain load came first."""
    load_edges(
        db_url, [_edge(_water(is_reconstructed=False, source_ref="w:1"))]
    )
    load_edges(db_url, [_edge(_water(is_reconstructed=True, source_ref="w:2"))])

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT is_reconstructed FROM lexeme WHERE headword = 'water'"
        ).fetchone()

    assert row is not None
    assert row[0] is True


def test_upsert_latest_wins_within_same_chunk(db_url: str) -> None:
    """Two edges to the same lexeme in one batch still resolve latest-wins."""
    edges = [
        _edge(_water(romanization=None, source_ref="w:1")),
        _edge(_water(romanization="water", source_ref="w:2")),
    ]

    load_edges(db_url, edges)

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT romanization, source_ref FROM lexeme "
            "WHERE headword = 'water'"
        ).fetchone()

    assert row is not None
    assert row[0] == "water"
    assert row[1] == "w:2"


def test_upsert_latest_wins_across_chunk_boundary(db_url: str) -> None:
    """Latest-wins coalesce holds across a chunk-commit boundary too."""
    edges = [
        _edge(_water(romanization=None, source_ref="w:1")),
        _edge(_water(romanization="water", source_ref="w:2")),
    ]

    load_edges(db_url, edges, chunk_size=1)

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT romanization, source_ref FROM lexeme "
            "WHERE headword = 'water'"
        ).fetchone()

    assert row is not None
    assert row[0] == "water"
    assert row[1] == "w:2"


def test_upsert_merges_same_etymology_number_into_two_senses(
    db_url: str,
) -> None:
    """Entries sharing etymology_number merge into one lexeme, many senses.

    Real record: en "underwater" adj/adv/noun all carry etymology_number
    "1" (one shared derivation, "under" + "water") but distinct pos/gloss --
    they must load as one lexeme row with two sense rows attached, not three
    separate same-labeled lexemes.
    """
    edges = [
        _edge(
            _water(
                etymology_number="1",
                pos="adj",
                gloss="beneath the surface of water",
                source_ref="w:1",
            )
        ),
        _edge(
            _water(
                etymology_number="1",
                pos="noun",
                gloss="the area beneath water",
                source_ref="w:2",
            )
        ),
    ]

    load_edges(db_url, edges)

    with psycopg.connect(db_url) as conn:
        lexemes = conn.execute(
            "SELECT id FROM lexeme WHERE headword = 'water'"
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

    Real record: en "underwater" verb carries etymology_number "2", a
    distinct derivation from the adj/adv/noun's "1" -- these must load as
    two separate lexeme rows, not merge.
    """
    edges = [
        _edge(_water(etymology_number="1", pos="adj", source_ref="w:1")),
        _edge(_water(etymology_number="2", pos="verb", source_ref="w:2")),
    ]

    load_edges(db_url, edges)

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT etymology_number FROM lexeme WHERE headword = 'water' "
            "ORDER BY etymology_number"
        ).fetchall()

    assert [row[0] for row in rows] == ["1", "2"]


def test_sense_upsert_is_idempotent(db_url: str) -> None:
    """Loading the exact same edge twice creates no duplicate sense row."""
    edge = _edge(_water(pos="noun", gloss="H2O", source_ref="w:1"))

    load_edges(db_url, [edge])
    load_edges(db_url, [edge])

    with psycopg.connect(db_url) as conn:
        row = conn.execute("SELECT count(*) FROM sense").fetchone()

    assert row is not None
    assert row[0] == 1


def test_load_handles_new_languages_across_chunk_boundaries(
    db_url: str,
) -> None:
    """A chunk's language upsert must not leak into its own lexeme upsert."""
    edges = [
        _edge(_water(gloss="H2O", source_ref="w:1")),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:2"),
            dst=Lexeme(lang_code="fr", headword="eau", source_ref="w:2"),
            rel_type=RelType.INHERITED,
            source_ref="w:2",
        ),
    ]

    load_edges(db_url, edges, chunk_size=1)

    with psycopg.connect(db_url) as conn:
        row = conn.execute("SELECT count(*) FROM lexeme").fetchone()

    assert row is not None
    assert row[0] == 4


class _FakeCursor:
    """Records executemany calls without touching a real database."""

    def __init__(self) -> None:
        self.calls: list[list[tuple[str, str, bool]]] = []

    def executemany(
        self,
        _query: str,
        rows: Iterable[tuple[str, str, bool]],
        *,
        returning: bool = False,
    ) -> None:
        del returning
        self.calls.append(list(rows))


def test_ensure_languages_skips_already_seen_codes() -> None:
    """A language code already loaded this run is never re-inserted."""
    cursor = _FakeCursor()
    seen = {"ine-pro"}
    edge = _edge(_water(source_ref="w:1"))

    _ensure_languages(cursor, [edge], seen)  # ty: ignore[invalid-argument-type]

    assert cursor.calls == [[("en", "en", False)]]
    assert seen == {"ine-pro", "en"}


def test_ensure_languages_marks_proto_language_codes() -> None:
    """A '-pro'-suffixed code is seeded with is_proto true."""
    cursor = _FakeCursor()
    edge = _edge(_water(source_ref="w:1"))

    _ensure_languages(cursor, [edge], set())  # ty: ignore[invalid-argument-type]

    assert ("ine-pro", "ine-pro", True) in cursor.calls[0]
    assert ("en", "en", False) in cursor.calls[0]


def test_ensure_languages_inserts_nothing_when_all_seen() -> None:
    """A chunk with no new language codes issues no insert at all."""
    cursor = _FakeCursor()
    seen = {"ine-pro", "en"}
    edge = _edge(_water(source_ref="w:1"))

    _ensure_languages(cursor, [edge], seen)  # ty: ignore[invalid-argument-type]

    assert cursor.calls == []
