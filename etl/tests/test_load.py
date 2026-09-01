"""DB-backed tests for the loader's upsert behavior."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import psycopg
import pytest

from etymyriad.load import (
    _DEFAULT_CHUNK_SIZE,
    _ensure_languages,
    _log_progress,
    _unique_lexemes,
    load_edges,
)
from etymyriad.model import EtymEdge, Lexeme, RelType, Sense


def test_schema_moves_pg_trgm_into_ext_schema(db_url: str) -> None:
    """pg_trgm lives in `ext`, so a schema-rename swap can't carry it
    away with whichever schema currently holds `public`.
    """
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT nspname FROM pg_extension "
            "JOIN pg_namespace "
            "  ON pg_namespace.oid = pg_extension.extnamespace "
            "WHERE extname = 'pg_trgm'"
        ).fetchone()

    assert row == ("ext",)


def test_schema_has_no_loaded_at_columns(db_url: str) -> None:
    """loaded_at (cross-run purge machinery) no longer exists."""
    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE column_name = 'loaded_at'"
        ).fetchall()

    assert rows == []


if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class _FakeClock:
    """Returns a fixed sequence of timestamps, one call at a time."""

    def __init__(self, times: list[float]) -> None:
        self._times = iter(times)

    def __call__(self) -> float:
        return next(self._times)


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

    load_edges(db_url, [compound_edge, *real_edges])

    with psycopg.connect(db_url) as conn:
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


@pytest.mark.parametrize(
    "chunk_size",
    [_DEFAULT_CHUNK_SIZE, 1],
    ids=["same-chunk", "chunk-boundary"],
)
def test_upsert_latest_wins(db_url: str, chunk_size: int) -> None:
    """Latest-wins coalesce holds whether or not a chunk boundary splits it."""
    edges = [
        _edge(_etymology(romanization=None, source_ref="w:1")),
        _edge(_etymology(romanization="etymology", source_ref="w:2")),
    ]

    load_edges(db_url, edges, chunk_size=chunk_size)

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT romanization, source_ref FROM lexeme "
            "WHERE headword = 'etymology'"
        ).fetchone()

    assert row is not None
    assert row[0] == "etymology"
    assert row[1] == "w:2"


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


def test_load_inserts_a_lone_lexeme_with_no_edges(db_url: str) -> None:
    """A zero-edge entry's own lexeme+senses load with no etymology row.

    Real record: en "con" etymology 3 ("Clipping of confidence trick")
    has a real sense but no ancestor-asserting template, so
    normalize() yields its lexeme on its own, not as an edge endpoint
    (ETYM-95). The loader must upsert it from that lone lexeme alone.
    """
    lexeme = _etymology(pos="noun", gloss="A confidence trick.")

    load_edges(db_url, [lexeme])

    with psycopg.connect(db_url) as conn:
        lexeme_row = conn.execute(
            "SELECT id FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()
        assert lexeme_row is not None
        sense_row = conn.execute(
            "SELECT gloss FROM sense WHERE lexeme_id = %s", (lexeme_row[0],)
        ).fetchone()
        edge_count = conn.execute("SELECT count(*) FROM etymology").fetchone()

    assert sense_row is not None
    assert sense_row[0] == "A confidence trick."
    assert edge_count is not None
    assert edge_count[0] == 0


def test_load_mixes_lone_lexemes_and_edges_in_one_chunk(db_url: str) -> None:
    """A chunk with both a lone lexeme and a real edge loads both."""
    lone = Lexeme(lang_code="en", headword="con", source_ref="w:lone")
    edge = _edge(_etymology(source_ref="w:1"))

    load_edges(db_url, [lone, edge])

    with psycopg.connect(db_url) as conn:
        headwords = {
            row[0]
            for row in conn.execute("SELECT headword FROM lexeme").fetchall()
        }

    assert headwords == {"con", "etymology", "leǵ-"}


def test_load_handles_new_languages_across_chunk_boundaries(
    db_url: str,
) -> None:
    """A chunk's language upsert must not leak into its own lexeme upsert."""
    edges = [
        _edge(_etymology(gloss="H2O", source_ref="w:1")),
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


def test_unique_lexemes_dedupes_a_shared_endpoint() -> None:
    """A src/dst reused across many edges in one chunk collapses to one.

    Real record: a common Latin root like "aqua" is the src of many
    descendant edges in the same chunk; it must be upserted once per
    chunk, not once per edge.
    """
    shared_dst = _etymology(source_ref="w:shared")
    edges = [
        _edge(shared_dst),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:2"),
            dst=shared_dst,
            rel_type=RelType.INHERITED,
            source_ref="w:2",
        ),
    ]

    result = _unique_lexemes(edges)

    assert result.count(_ANCESTOR) == 1
    assert result.count(shared_dst) == 1
    assert len(result) == 3


def test_unique_lexemes_keeps_distinct_lexemes_separate() -> None:
    """Lexemes that differ in any field are not collapsed together."""
    edges = [
        _edge(_etymology(source_ref="w:1")),
        _edge(_etymology(romanization="etymology", source_ref="w:2")),
    ]

    result = _unique_lexemes(edges)

    assert len(result) == 3  # shared ancestor + two distinct dsts


def test_load_edges_writes_checkpoint_after_each_committed_chunk(
    db_url: str, tmp_path: Path
) -> None:
    """Progress persists so a crash mid-load can resume past what committed."""
    checkpoint = tmp_path / "load.checkpoint"
    edges = [
        _edge(_etymology(source_ref="w:1")),
        _edge(_etymology(romanization="etymology", source_ref="w:2")),
    ]

    load_edges(db_url, edges, chunk_size=1, checkpoint_path=checkpoint)

    payload = json.loads(checkpoint.read_text())
    assert payload["count"] == 2
    assert payload["run_started_at"]


def test_load_edges_checkpoint_reflects_only_committed_chunks_on_crash(
    db_url: str, tmp_path: Path
) -> None:
    """A failure partway through leaves the checkpoint at the last commit."""
    checkpoint = tmp_path / "load.checkpoint"
    good = _edge(_etymology(source_ref="w:1"))

    def _edges() -> Iterable[EtymEdge]:
        yield good
        msg = "boom"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="boom"):
        load_edges(db_url, _edges(), chunk_size=1, checkpoint_path=checkpoint)

    assert json.loads(checkpoint.read_text())["count"] == 1


def test_load_edges_resumes_from_checkpoint(
    db_url: str, tmp_path: Path
) -> None:
    """A checkpoint count skips its already-loaded prefix on resume."""
    checkpoint = tmp_path / "load.checkpoint"
    checkpoint.write_text(
        json.dumps({"count": 1, "run_started_at": "2026-01-01T00:00:00+00:00"})
    )
    edges = [
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:1"),
            dst=Lexeme(lang_code="es", headword="agua", source_ref="w:1"),
            rel_type=RelType.INHERITED,
            source_ref="w:1",
        ),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="terra", source_ref="w:2"),
            dst=Lexeme(lang_code="es", headword="tierra", source_ref="w:2"),
            rel_type=RelType.INHERITED,
            source_ref="w:2",
        ),
    ]

    loaded = load_edges(db_url, edges, checkpoint_path=checkpoint)

    assert loaded == 2
    with psycopg.connect(db_url) as conn:
        headwords = {
            row[0]
            for row in conn.execute("SELECT headword FROM lexeme").fetchall()
        }
    assert headwords == {"terra", "tierra"}


class _FakeCursor:
    """Records executemany calls without touching a real database."""

    def __init__(self) -> None:
        self.calls: list[list[tuple[str, str, str | None, bool]]] = []

    def executemany(
        self,
        _query: str,
        rows: Iterable[tuple[str, str, str | None, bool]],
        *,
        returning: bool = False,
    ) -> None:
        del returning
        self.calls.append(list(rows))


def test_ensure_languages_skips_already_seen_codes() -> None:
    """A language code already loaded this run is never re-inserted."""
    cursor = _FakeCursor()
    seen = {"ine-pro"}
    edge = _edge(_etymology(source_ref="w:1"))

    _ensure_languages(cursor, [edge], seen)  # ty: ignore[invalid-argument-type]

    assert cursor.calls == [[("en", "English", "Germanic", False)]]
    assert seen == {"ine-pro", "en"}


def test_ensure_languages_marks_proto_language_codes() -> None:
    """A '-pro'-suffixed code is seeded with is_proto true."""
    cursor = _FakeCursor()
    edge = _edge(_etymology(source_ref="w:1"))

    _ensure_languages(cursor, [edge], set())  # ty: ignore[invalid-argument-type]

    assert (
        "ine-pro",
        "Proto-Indo-European",
        "Indo-European",
        True,
    ) in cursor.calls[0]
    assert ("en", "English", "Germanic", False) in cursor.calls[0]


def test_ensure_languages_falls_back_to_code_when_name_unmapped() -> None:
    """A code the dump never named (e.g. ancestor-only) uses the code."""
    cursor = _FakeCursor()
    edge = EtymEdge(
        src=Lexeme(
            lang_code="xx-nonexistent",
            headword="foo",
            source_ref="w:1",
        ),
        dst=_etymology(source_ref="w:1"),
        rel_type=RelType.INHERITED,
        source_ref="w:1",
    )

    _ensure_languages(cursor, [edge], set())  # ty: ignore[invalid-argument-type]

    assert (
        "xx-nonexistent",
        "xx-nonexistent",
        None,
        False,
    ) in cursor.calls[0]


def test_ensure_languages_inserts_nothing_when_all_seen() -> None:
    """A chunk with no new language codes issues no insert at all."""
    cursor = _FakeCursor()
    seen = {"ine-pro", "en"}
    edge = _edge(_etymology(source_ref="w:1"))

    _ensure_languages(cursor, [edge], seen)  # ty: ignore[invalid-argument-type]

    assert cursor.calls == []


def test_ensure_languages_logs_debug_for_new_language_batch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A batch of new language codes logs at DEBUG, e.g. for verbose runs."""
    cursor = _FakeCursor()
    edge = _edge(_etymology(source_ref="w:1"))

    with caplog.at_level(logging.DEBUG, logger="etymyriad.load"):
        _ensure_languages(cursor, [edge], set())  # ty: ignore[invalid-argument-type]

    messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("ine-pro" in m and "en" in m for m in messages)


def test_log_progress_uses_thousands_separators(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A large count reads as "10,287,531", not "10287531"."""
    with caplog.at_level(logging.INFO, logger="etymyriad.load"):
        _log_progress(10_287_531, 6_584_600, 1000.0)

    message = caplog.records[0].message
    assert "10,287,531 edges" in message
    assert "3,702 edges/sec" in message


def test_load_edges_logs_progress_on_first_and_last_chunk(
    db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """First and last chunk log progress even if no interval has elapsed."""
    edges = [
        _edge(_etymology(etymology_number=str(i), source_ref=f"w:{i}"))
        for i in range(3)
    ]
    # One clock() call before the loop, then one per chunk (3 chunks); the
    # clock never advances, so only the forced first/last logs should fire.
    clock = _FakeClock([0.0, 0.0, 0.0, 0.0])

    with caplog.at_level(logging.INFO, logger="etymyriad.load"):
        load_edges(db_url, edges, chunk_size=1, clock=clock)

    progress = [r.message for r in caplog.records if "loaded" in r.message]
    assert len(progress) == 2
    assert "1 edges" in progress[0]
    assert "3 edges" in progress[1]


def test_load_edges_logs_progress_on_interval_schedule(
    db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A chunk finishing past the progress interval logs early, mid-load."""
    edges = [
        _edge(_etymology(etymology_number=str(i), source_ref=f"w:{i}"))
        for i in range(4)
    ]
    # init, chunk0, chunk1, chunk2, chunk3. Chunk2 crosses the 10s interval
    # from chunk0's log; chunk1 and chunk3 don't cross it from their prior
    # log, so chunk3 is only logged via the unconditional last-chunk log.
    clock = _FakeClock([0.0, 0.0, 3.0, 11.0, 11.0])

    with caplog.at_level(logging.INFO, logger="etymyriad.load"):
        load_edges(db_url, edges, chunk_size=1, clock=clock)

    progress = [r.message for r in caplog.records if "loaded" in r.message]
    assert len(progress) == 3
    assert "1 edges" in progress[0]
    assert "3 edges" in progress[1]
    assert "4 edges" in progress[2]


def test_load_edges_logs_checkpoint_resume_skip_count(
    db_url: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Resuming from a checkpoint logs how many edges it's skipping."""
    checkpoint = tmp_path / "load.checkpoint"
    checkpoint.write_text(
        json.dumps({"count": 1, "run_started_at": "2026-01-01T00:00:00+00:00"})
    )
    edges = [
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:1"),
            dst=Lexeme(lang_code="es", headword="agua", source_ref="w:1"),
            rel_type=RelType.INHERITED,
            source_ref="w:1",
        ),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="terra", source_ref="w:2"),
            dst=Lexeme(lang_code="es", headword="tierra", source_ref="w:2"),
            rel_type=RelType.INHERITED,
            source_ref="w:2",
        ),
    ]

    with caplog.at_level(logging.INFO, logger="etymyriad.load"):
        load_edges(db_url, edges, checkpoint_path=checkpoint)

    resume_logs = [r.message for r in caplog.records if "skipping" in r.message]
    assert len(resume_logs) == 1
    assert "1" in resume_logs[0]


def test_load_edges_logs_checkpoint_resume_skip_count_with_commas(
    db_url: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A large skip count reads as "12,345", not "12345"."""
    checkpoint = tmp_path / "load.checkpoint"
    checkpoint.write_text(
        json.dumps({
            "count": 12_345,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        })
    )

    with caplog.at_level(logging.INFO, logger="etymyriad.load"):
        load_edges(db_url, [], checkpoint_path=checkpoint)

    resume_logs = [r.message for r in caplog.records if "skipping" in r.message]
    assert len(resume_logs) == 1
    assert "12,345" in resume_logs[0]


def test_load_edges_logs_error_on_chunk_failure_before_raising(
    db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A chunk that fails logs its index and in-flight count first."""
    good = _edge(_etymology(source_ref="w:1"))

    def _edges() -> Iterable[EtymEdge]:
        yield good
        msg = "boom"
        raise RuntimeError(msg)

    with (
        caplog.at_level(logging.ERROR, logger="etymyriad.load"),
        pytest.raises(RuntimeError, match="boom"),
    ):
        load_edges(db_url, _edges(), chunk_size=1)

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "1" in errors[0].message  # chunk index 1 (0-indexed, second chunk)


def test_load_edges_logs_error_on_db_failure_before_raising(
    db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A chunk rejected by the DB itself (not the edge source) also logs."""
    same = _etymology(source_ref="w:1")
    self_loop = EtymEdge(
        src=same,
        dst=same,
        rel_type=RelType.INHERITED,
        source_ref="w:1",
    )

    with (
        caplog.at_level(logging.ERROR, logger="etymyriad.load"),
        pytest.raises(psycopg.errors.CheckViolation),
    ):
        load_edges(db_url, [self_loop])

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "0" in errors[0].message  # chunk index 0, first and only chunk
    assert "1" in errors[0].message  # 1 edge in flight


def test_purge_deletes_lexeme_untouched_by_a_later_load(db_url: str) -> None:
    """A headword dropped from the source dump doesn't linger forever."""
    load_edges(db_url, [_edge(_etymology(source_ref="w:1"))])
    load_edges(
        db_url,
        [
            EtymEdge(
                src=Lexeme(lang_code="la", headword="aqua", source_ref="w:2"),
                dst=Lexeme(lang_code="fr", headword="eau", source_ref="w:2"),
                rel_type=RelType.INHERITED,
                source_ref="w:2",
            )
        ],
    )

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT count(*) FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()

    assert row is not None
    assert row[0] == 0


def test_purge_keeps_lexeme_reloaded_by_a_later_run(db_url: str) -> None:
    """A headword still present in every load survives every purge."""
    edge = _edge(_etymology(source_ref="w:1"))

    load_edges(db_url, [edge])
    load_edges(db_url, [edge])

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT count(*) FROM lexeme WHERE headword = 'etymology'"
        ).fetchone()

    assert row is not None
    assert row[0] == 1


def test_purge_deletes_stale_edge_whose_endpoints_stay_fresh(
    db_url: str,
) -> None:
    """A dropped template's edge is purged even if both endpoints persist.

    Both edges below share the same src/dst pair; only the INHERITED
    one reappears in the second load, so the lexeme rows stay fresh
    and only an explicit etymology delete (not a lexeme cascade) can
    remove the DERIVED edge that fell out of the dump.
    """
    dst = _etymology(source_ref="w:1")
    stale_edge = EtymEdge(
        src=_ANCESTOR, dst=dst, rel_type=RelType.DERIVED, source_ref="w:1"
    )
    surviving_edge = EtymEdge(
        src=_ANCESTOR, dst=dst, rel_type=RelType.INHERITED, source_ref="w:2"
    )

    load_edges(db_url, [stale_edge, surviving_edge])
    load_edges(db_url, [surviving_edge])

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT rel_type FROM etymology e "
            "JOIN lexeme l ON l.id = e.src_id WHERE l.headword = 'leǵ-'"
        ).fetchall()

    assert [row[0] for row in rows] == ["inherited"]


def test_purge_deletes_stale_sense_whose_lexeme_stays_fresh(
    db_url: str,
) -> None:
    """A dropped sense is purged even though its lexeme is still loaded."""
    load_edges(
        db_url,
        [_edge(_etymology(pos="noun", gloss="stale", source_ref="w:1"))],
    )
    load_edges(
        db_url,
        [_edge(_etymology(pos="noun", gloss="current", source_ref="w:2"))],
    )

    with psycopg.connect(db_url) as conn:
        rows = conn.execute("SELECT gloss FROM sense").fetchall()

    assert [row[0] for row in rows] == ["current"]


def test_purge_uses_checkpoint_persisted_run_started_at(
    db_url: str, tmp_path: Path
) -> None:
    """A crash-and-resume keeps every chunk's rows under one run's stamp.

    If a resumed load minted a fresh run_started_at instead of reusing
    the one persisted at the crash, the purge threshold would land
    after the pre-crash chunk's rows (real wall-clock time always
    advances between the two load_edges calls below), deleting a
    chunk that already committed successfully.
    """
    checkpoint = tmp_path / "load.checkpoint"
    first = _edge(_etymology(source_ref="w:1"))
    second = _edge(_etymology(etymology_number="2", source_ref="w:2"))

    load_edges(db_url, [first], chunk_size=1, checkpoint_path=checkpoint)
    load_edges(
        db_url, [first, second], chunk_size=1, checkpoint_path=checkpoint
    )

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT etymology_number FROM lexeme "
            "WHERE headword = 'etymology' ORDER BY etymology_number"
        ).fetchall()

    assert [row[0] for row in rows] == ["2", None]


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
