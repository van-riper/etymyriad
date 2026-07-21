"""Upsert the etymology graph into Postgres.

Idempotent: re-running with the same data produces the same rows. Lexemes are
upserted on their natural key, edges on (src, dst, rel_type). Each chunk is
sent as one batch (psycopg pipelines the statements) and committed on its
own, so a large load neither holds one giant transaction nor pays a network
round trip per row.
"""

from __future__ import annotations

import logging
import time
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
    ON CONFLICT (code) DO NOTHING
"""

_LEXEME_UPSERT_SQL = """
    INSERT INTO lexeme (lang_code, headword, etymology_number, romanization,
                        is_reconstructed, source_ref)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (lang_code, headword, etym_key)
    DO UPDATE SET
        romanization = COALESCE(EXCLUDED.romanization,
                                lexeme.romanization),
        is_reconstructed = lexeme.is_reconstructed
                           OR EXCLUDED.is_reconstructed,
        source_ref = EXCLUDED.source_ref
    RETURNING id
"""

_SENSE_UPSERT_SQL = """
    INSERT INTO sense (lexeme_id, pos, gloss, source_ref)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (lexeme_id, pos_key, gloss_key)
    DO UPDATE SET source_ref = EXCLUDED.source_ref
"""

_EDGE_UPSERT_SQL = """
    INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (src_id, dst_id, rel_type) DO NOTHING
"""


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

    Args:
        database_url: Postgres connection string.
        edges: The etymology edges to load.
        chunk_size: How many edges to batch and commit at a time.
        checkpoint_path: When given, the count of already-loaded edges is
            read from this path before starting (skipping that many edges)
            and written back after every committed chunk, so a crashed
            load can resume instead of redoing already-committed writes.
        clock: Timestamp source for progress-interval logging. Overridable
            in tests; production code should never pass this.

    Returns:
        The number of edges processed, including any skipped via a
        checkpoint from a prior run.
    """
    count = _read_checkpoint(checkpoint_path)
    if count:
        _log.info("resuming from checkpoint, skipping %d edges", count)
        edges = islice(edges, count, None)

    seen_languages: set[str] = set()
    chunk_was_logged = False
    now = last_log_time = clock()
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
                count += _load_chunk(cursor, chunk, seen_languages)
            except Exception:
                _log.error(
                    "chunk %d failed, %d edges in flight",
                    chunk_index,
                    count + len(chunk),
                )
                raise
            connection.commit()
            _write_checkpoint(checkpoint_path, count)

            now = clock()
            elapsed = now - last_log_time
            chunk_was_logged = (
                chunk_index == 0 or elapsed >= _PROGRESS_INTERVAL_SECONDS
            )
            if chunk_was_logged:
                _log_progress(count, count_at_last_log, elapsed)
                last_log_time = now
                count_at_last_log = count
            chunk_index += 1

        if chunk_index and not chunk_was_logged:
            _log_progress(count, count_at_last_log, now - last_log_time)

    return count


def _log_progress(count: int, count_at_last_log: int, elapsed: float) -> None:
    rate = (count - count_at_last_log) / elapsed if elapsed > 0 else 0.0
    _log.info("loaded %d edges (%.1f edges/sec)", count, rate)


def _read_checkpoint(path: str | Path | None) -> int:
    if path is None:
        return 0
    checkpoint = Path(path)
    try:
        return int(checkpoint.read_text(encoding="utf-8").strip())
    except FileNotFoundError:
        return 0


def _write_checkpoint(path: str | Path | None, count: int) -> None:
    if path is None:
        return
    Path(path).write_text(str(count), encoding="utf-8")


def _chunked(edges: Iterable[EtymEdge], size: int) -> Iterator[list[EtymEdge]]:
    it = iter(edges)
    while batch := list(islice(it, size)):
        yield batch


def _load_chunk(
    cursor: psycopg.Cursor,
    chunk: list[EtymEdge],
    seen_languages: set[str],
) -> int:
    with cursor.connection.pipeline():
        _ensure_languages(cursor, chunk, seen_languages)

        lexemes = _unique_lexemes(chunk)
        ids = _upsert_lexemes(cursor, [_lexeme_row(lex) for lex in lexemes])
        id_by_lexeme = dict(zip(lexemes, ids, strict=True))

        sense_rows = [
            (id_by_lexeme[lexeme], sense.pos, sense.gloss, sense.source_ref)
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


def _lexeme_row(lexeme: Lexeme) -> tuple[object, ...]:
    return (
        lexeme.lang_code,
        lexeme.headword,
        lexeme.etymology_number,
        lexeme.romanization,
        lexeme.is_reconstructed,
        lexeme.source_ref,
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
