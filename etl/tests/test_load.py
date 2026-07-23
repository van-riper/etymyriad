"""DB-backed tests for the loader's upsert behavior."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import psycopg
import pytest

from etymyriad.load import (
    _DEFAULT_CHUNK_SIZE,
    _ensure_languages,
    _unique_lexemes,
    load_edges,
)
from etymyriad.model import EtymEdge, Lexeme, RelType, Sense

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


def _etymology(  # noqa: PLR0913 - test builder, one kwarg per Lexeme field
    *,
    gloss: str | None = None,
    pos: str | None = None,
    etymology_number: str | None = None,
    romanization: str | None = None,
    is_reconstructed: bool = False,
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

    assert checkpoint.read_text() == "2"


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

    assert checkpoint.read_text() == "1"


def test_load_edges_resumes_from_checkpoint(
    db_url: str, tmp_path: Path
) -> None:
    """A checkpoint count skips its already-loaded prefix on resume."""
    checkpoint = tmp_path / "load.checkpoint"
    checkpoint.write_text("1")
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
    checkpoint.write_text("1")
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
