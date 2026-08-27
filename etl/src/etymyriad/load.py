"""Upsert the etymology graph into Postgres.

Idempotent: re-running with the same data produces the same rows. Lexemes are
upserted on their natural key, edges on (src, dst, rel_type). Each chunk is
sent as one batch (psycopg pipelines the statements) and committed on its
own, so a large load neither holds one giant transaction nor pays a network
round trip per row.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

import psycopg

from etymyriad.languages import language_family, language_name
from etymyriad.model import PROTO_LANG_SUFFIX

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from uuid import UUID

    from etymyriad.model import EtymEdge, Lexeme

_log = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 1000
_PROGRESS_INTERVAL_SECONDS = 10

_LANGUAGE_UPSERT_SQL = """
    INSERT INTO language (code, name, lang_family, is_proto)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (code) DO UPDATE SET
        name = EXCLUDED.name,
        lang_family = EXCLUDED.lang_family,
        is_proto = EXCLUDED.is_proto
"""

_LEXEME_UPSERT_SQL = """
    INSERT INTO lexeme (lang_code, headword, etymology_number, romanization,
                        is_reconstructed, is_redlink, source_ref, loaded_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (lang_code, headword, etym_key)
    DO UPDATE SET
        romanization = COALESCE(EXCLUDED.romanization,
                                lexeme.romanization),
        is_reconstructed = lexeme.is_reconstructed
                           OR EXCLUDED.is_reconstructed,
        is_redlink = lexeme.is_redlink AND EXCLUDED.is_redlink,
        source_ref = EXCLUDED.source_ref,
        loaded_at = EXCLUDED.loaded_at
    RETURNING id
"""

_SENSE_UPSERT_SQL = """
    INSERT INTO sense (lexeme_id, pos, gloss, source_ref, loaded_at)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (lexeme_id, pos_key, gloss_key)
    DO UPDATE SET
        source_ref = EXCLUDED.source_ref,
        loaded_at = EXCLUDED.loaded_at
"""

_CLEAR_STALE_REDLINKS_SQL = """
    UPDATE lexeme SET is_redlink = false
    WHERE is_redlink
      AND EXISTS (
          SELECT 1 FROM lexeme AS real_entry
          WHERE real_entry.lang_code = lexeme.lang_code
            AND real_entry.headword = lexeme.headword
            AND NOT real_entry.is_redlink
      )
"""

# A template reference with no etymology_number can't say which of a
# split headword's sections it means, so it lands on an unnumbered stub
# that never collides with any of them.
# Once a real, numbered sibling exists, resolve the stub onto the
# lowest-numbered one (Wiktionary orders etymology sections for a
# reason, and the first is the best deterministic guess available
# without inventing a fact) by moving every edge that touches the stub
# onto that sibling, then deleting the stub. An edge is left on the
# stub, and the stub left undeleted, when moving it would create a
# self-loop -- a template can cite its own headword unnumbered
# specifically to point at a *different* section of itself (e.g.
# {{der|pt|pt|matreira|pos=etymology 1}} on "matreira" itself), and if
# that different section happens to be the lowest-numbered one, this is
# how that citation resolves back onto the same section that made it.
_MERGE_SPLIT_STUB_LEXEMES_SQL = """
    WITH target AS (
        SELECT DISTINCT ON (stub.id)
            stub.id AS stub_id, real_entry.id AS real_id
        FROM lexeme AS stub
        JOIN lexeme AS real_entry
          ON real_entry.lang_code = stub.lang_code
         AND real_entry.headword = stub.headword
         AND NOT real_entry.is_redlink
         AND real_entry.etym_key <> ''
        WHERE stub.is_redlink
          AND stub.etym_key = ''
        ORDER BY stub.id, real_entry.etymology_number ASC
    ),
    reassign_outgoing AS (
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref,
                               piece_order, loaded_at)
        SELECT target.real_id, e.dst_id, e.rel_type, e.source_ref,
               e.piece_order, e.loaded_at
        FROM etymology AS e
        JOIN target ON target.stub_id = e.src_id
        WHERE target.real_id <> e.dst_id
        ON CONFLICT (src_id, dst_id, rel_type) DO UPDATE SET
            loaded_at = EXCLUDED.loaded_at
    ),
    reassign_incoming AS (
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref,
                               piece_order, loaded_at)
        SELECT e.src_id, target.real_id, e.rel_type, e.source_ref,
               e.piece_order, e.loaded_at
        FROM etymology AS e
        JOIN target ON target.stub_id = e.dst_id
        WHERE target.real_id <> e.src_id
        ON CONFLICT (src_id, dst_id, rel_type) DO UPDATE SET
            loaded_at = EXCLUDED.loaded_at
    ),
    safe_to_delete AS (
        SELECT target.stub_id
        FROM target
        WHERE NOT EXISTS (
            SELECT 1 FROM etymology AS e
            WHERE (e.src_id = target.stub_id AND e.dst_id = target.real_id)
               OR (e.dst_id = target.stub_id AND e.src_id = target.real_id)
        )
    )
    DELETE FROM lexeme WHERE id IN (SELECT stub_id FROM safe_to_delete)
"""

_EDGE_UPSERT_SQL = """
    INSERT INTO etymology (src_id, dst_id, rel_type, source_ref,
                           piece_order, loaded_at)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (src_id, dst_id, rel_type) DO UPDATE SET
        piece_order = EXCLUDED.piece_order,
        loaded_at = EXCLUDED.loaded_at
"""

# A row older than the current run's start time was never touched this
# run -- deleting etymology/sense explicitly (rather than relying on
# lexeme's ON DELETE CASCADE) also catches a row whose lexeme endpoint
# stayed fresh through some other edge/sense this run.
_PURGE_STALE_ETYMOLOGY_SQL = "DELETE FROM etymology WHERE loaded_at < %s"
_PURGE_STALE_SENSE_SQL = "DELETE FROM sense WHERE loaded_at < %s"
_PURGE_STALE_LEXEME_SQL = "DELETE FROM lexeme WHERE loaded_at < %s"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def load_edges(
    database_url: str,
    edges: Iterable[EtymEdge],
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    checkpoint_path: str | Path | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Upsert edges and their endpoint lexemes into Postgres.

    Idempotent: lexemes upsert on their natural key and edges on
    (src_id, dst_id, rel_type), so re-running the same input adds no
    duplicate rows. A failure partway through leaves earlier chunks
    committed rather than rolling back the whole load; safe to re-run.
    Also merges an unnumbered reference stub onto its real, numbered
    sibling once one exists, and clears is_redlink on any lexeme whose
    headword now has a non-redlink sibling from an earlier load,
    regardless of etymology_number.

    Every row this run touches is stamped with a single run_started_at
    timestamp, captured once and reused across every chunk (and across a
    checkpoint resume). Once every chunk commits, any lexeme, etymology,
    or sense row stamped from an earlier run is deleted, so a headword or
    edge the source dump no longer produces doesn't linger forever.

    Args:
        database_url: Postgres connection string.
        edges: The etymology edges to load.
        chunk_size: How many edges to batch and commit at a time.
        checkpoint_path: When given, the count of already-loaded edges and
            this run's start time are read from this path before starting
            (skipping that many edges and reusing that start time) and
            written back after every committed chunk, so a crashed load
            can resume instead of redoing already-committed writes, and
            the eventual purge doesn't delete the crashed run's own rows.
        clock: Timestamp source for progress-interval logging. Overridable
            in tests; production code should never pass this.

    Returns:
        The number of edges processed, including any skipped via a
        checkpoint from a prior run.
    """
    count, run_started_at = _read_checkpoint(checkpoint_path)
    if run_started_at is None:
        run_started_at = _utcnow()
    if count:
        _log.info("resuming from checkpoint, skipping %d edges", count)
        edges = islice(edges, count, None)

    seen_languages: set[str] = set()
    chunk_was_logged = False
    tick = last_log_time = clock()
    count_at_last_log = count

    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        chunks = _chunked(edges, chunk_size)
        chunk_index = 0
        while True:
            try:
                chunk = next(chunks)
            except StopIteration:
                break
            except Exception:
                _log.error(
                    "chunk %d failed, %d edges in flight", chunk_index, count
                )
                raise

            try:
                count += _load_chunk(
                    cursor, chunk, seen_languages, run_started_at
                )
            except Exception:
                _log.error(
                    "chunk %d failed, %d edges in flight",
                    chunk_index,
                    count + len(chunk),
                )
                raise
            connection.commit()
            _write_checkpoint(checkpoint_path, count, run_started_at)

            tick = clock()
            elapsed = tick - last_log_time
            chunk_was_logged = (
                chunk_index == 0 or elapsed >= _PROGRESS_INTERVAL_SECONDS
            )
            if chunk_was_logged:
                _log_progress(count, count_at_last_log, elapsed)
                last_log_time = tick
                count_at_last_log = count
            chunk_index += 1

        if chunk_index and not chunk_was_logged:
            _log_progress(count, count_at_last_log, tick - last_log_time)

        _merge_split_stub_lexemes(cursor)
        _clear_stale_redlinks(cursor)
        _purge_stale_rows(cursor, run_started_at)
        connection.commit()

    return count


def _purge_stale_rows(cursor: psycopg.Cursor, run_started_at: datetime) -> None:
    """Delete lexeme/etymology/sense rows this run never touched."""
    cursor.execute(_PURGE_STALE_ETYMOLOGY_SQL, (run_started_at,))
    cursor.execute(_PURGE_STALE_SENSE_SQL, (run_started_at,))
    cursor.execute(_PURGE_STALE_LEXEME_SQL, (run_started_at,))


def _merge_split_stub_lexemes(cursor: psycopg.Cursor) -> None:
    """Fold an unnumbered reference stub into its real, numbered sibling.

    Must run before the redlink-flag cleanup that follows: clearing the
    flag alone can't fix the split-headword gap, since it never
    reconnects the stub's edges to a real entry. Any stub this leaves
    behind (unsafe to delete, since folding it in would create a
    self-loop) still gets its flag cleared by that later step.
    """
    cursor.execute(_MERGE_SPLIT_STUB_LEXEMES_SQL)


def _clear_stale_redlinks(cursor: psycopg.Cursor) -> None:
    """Clear a headword's redlink once a real entry exists for it.

    The per-chunk upsert's AND-latch only fires when a real entry
    shares the exact natural key, so a headword split by
    etymology_number (multiple numbered entries, no unnumbered one)
    never collides with its own unnumbered redlink stub.
    """
    cursor.execute(_CLEAR_STALE_REDLINKS_SQL)


def _log_progress(count: int, count_at_last_log: int, elapsed: float) -> None:
    rate = (count - count_at_last_log) / elapsed if elapsed > 0 else 0.0
    _log.info("loaded %d edges (%.1f edges/sec)", count, rate)


def _read_checkpoint(
    path: str | Path | None,
) -> tuple[int, datetime | None]:
    if path is None:
        return 0, None
    checkpoint = Path(path)
    try:
        raw = checkpoint.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 0, None
    payload = json.loads(raw)
    return payload["count"], datetime.fromisoformat(payload["run_started_at"])


def _write_checkpoint(
    path: str | Path | None, count: int, run_started_at: datetime
) -> None:
    if path is None:
        return
    payload = {"count": count, "run_started_at": run_started_at.isoformat()}
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


def _chunked(edges: Iterable[EtymEdge], size: int) -> Iterator[list[EtymEdge]]:
    it = iter(edges)
    while batch := list(islice(it, size)):
        yield batch


def _load_chunk(
    cursor: psycopg.Cursor,
    chunk: list[EtymEdge],
    seen_languages: set[str],
    run_started_at: datetime,
) -> int:
    with cursor.connection.pipeline():
        _ensure_languages(cursor, chunk, seen_languages)

        lexemes = _unique_lexemes(chunk)
        ids = _upsert_lexemes(
            cursor, [_lexeme_row(lex, run_started_at) for lex in lexemes]
        )
        id_by_lexeme = dict(zip(lexemes, ids, strict=True))

        sense_rows = [
            (
                id_by_lexeme[lexeme],
                sense.pos,
                sense.gloss,
                sense.source_ref,
                run_started_at,
            )
            for lexeme in lexemes
            for sense in lexeme.senses
        ]
        if sense_rows:
            cursor.executemany(_SENSE_UPSERT_SQL, sense_rows, returning=True)

        edge_rows = [
            (
                id_by_lexeme[edge.src],
                id_by_lexeme[edge.dst],
                edge.rel_type.value,
                edge.source_ref,
                edge.piece_order,
                run_started_at,
            )
            for edge in chunk
        ]
        cursor.executemany(_EDGE_UPSERT_SQL, edge_rows, returning=True)
    return len(chunk)


def _unique_lexemes(chunk: Iterable[EtymEdge]) -> list[Lexeme]:
    """Distinct lexemes referenced by `chunk`, in first-seen order.

    Multiple edges in a chunk often share an endpoint (a common ancestor
    borrowed into many descendants, or one entry's several templates all
    pointing back at the same descendant); deduping here means each
    distinct lexeme is upserted once per chunk instead of once per edge.

    Returns:
        The distinct lexemes referenced by `chunk`, in first-seen order.
    """
    unique: dict[Lexeme, None] = {}
    for edge in chunk:
        unique[edge.src] = None
        unique[edge.dst] = None
    return list(unique)


def _ensure_languages(
    cursor: psycopg.Cursor,
    chunk: list[EtymEdge],
    seen_languages: set[str],
) -> None:
    """Insert any language codes in `chunk` not already loaded this run."""
    new_codes = {
        code
        for edge in chunk
        for code in (edge.src.lang_code, edge.dst.lang_code)
        if code not in seen_languages
    }
    if not new_codes:
        return
    _log.debug(
        "upserting %d new language(s): %s",
        len(new_codes),
        sorted(new_codes),
    )
    cursor.executemany(
        _LANGUAGE_UPSERT_SQL,
        [
            (
                code,
                language_name(code) or code,
                language_family(code),
                code.endswith(PROTO_LANG_SUFFIX),
            )
            for code in new_codes
        ],
        returning=True,
    )
    seen_languages.update(new_codes)


def _lexeme_row(lexeme: Lexeme, run_started_at: datetime) -> tuple[object, ...]:
    return (
        lexeme.lang_code,
        lexeme.headword,
        lexeme.etymology_number,
        lexeme.romanization,
        lexeme.is_reconstructed,
        lexeme.is_redlink,
        lexeme.source_ref,
        run_started_at,
    )


def _upsert_lexemes(
    cursor: psycopg.Cursor, rows: list[tuple[object, ...]]
) -> list[UUID]:
    """Upsert lexemes, returning their ids in the same order as `rows`.

    Returns:
        The upserted ids, one per row, in `rows` order.

    Raises:
        RuntimeError: If any upsert returns no id.
    """
    cursor.executemany(_LEXEME_UPSERT_SQL, rows, returning=True)
    ids: list[UUID] = []
    while True:
        row = cursor.fetchone()
        if row is None:
            msg = "lexeme upsert returned no id"
            raise RuntimeError(msg)
        ids.append(row[0])
        if not cursor.nextset():
            break
    return ids
