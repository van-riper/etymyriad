"""Upsert the etymology graph into Postgres.

Idempotent: re-running with the same data produces the same rows. Lexemes are
upserted on their natural key, edges on (src, dst, rel_type). Each chunk is
sent as one batch (psycopg pipelines the statements) and committed on its
own, so a large load neither holds one giant transaction nor pays a network
round trip per row.
"""

from __future__ import annotations

from itertools import islice
from typing import TYPE_CHECKING

import psycopg

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from etymyriad.model import EtymEdge, Lexeme

_DEFAULT_CHUNK_SIZE = 1000

_LANGUAGE_UPSERT_SQL = """
    INSERT INTO language (code, name)
    VALUES (%s, %s)
    ON CONFLICT (code) DO NOTHING
"""

_LEXEME_UPSERT_SQL = """
    INSERT INTO lexeme (lang_code, headword, gloss, romanization, pos,
                        is_reconstructed, source_ref)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (lang_code, headword, COALESCE(gloss, ''))
    DO UPDATE SET
        pos = COALESCE(EXCLUDED.pos, lexeme.pos),
        romanization = COALESCE(EXCLUDED.romanization,
                                lexeme.romanization),
        is_reconstructed = lexeme.is_reconstructed
                           OR EXCLUDED.is_reconstructed,
        source_ref = EXCLUDED.source_ref
    RETURNING id
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

    Returns:
        The number of edges processed.
    """
    count = 0
    seen_languages: set[str] = set()
    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        for chunk in _chunked(edges, chunk_size):
            count += _load_chunk(cursor, chunk, seen_languages)
            connection.commit()

    return count


def _chunked(edges: Iterable[EtymEdge], size: int) -> Iterator[list[EtymEdge]]:
    it = iter(edges)
    while batch := list(islice(it, size)):
        yield batch


def _load_chunk(
    cursor: psycopg.Cursor,
    chunk: list[EtymEdge],
    seen_languages: set[str],
) -> int:
    _ensure_languages(cursor, chunk, seen_languages)

    lexeme_rows: list[tuple[object, ...]] = []
    for edge in chunk:
        lexeme_rows.extend((_lexeme_row(edge.src), _lexeme_row(edge.dst)))
    ids = _upsert_lexemes(cursor, lexeme_rows)

    edge_rows = [
        (ids[2 * i], ids[2 * i + 1], edge.rel_type.value, edge.source_ref)
        for i, edge in enumerate(chunk)
    ]
    cursor.executemany(_EDGE_UPSERT_SQL, edge_rows)
    return len(chunk)


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
    cursor.executemany(
        _LANGUAGE_UPSERT_SQL,
        [(code, code) for code in new_codes],  # name backfilled later
    )
    seen_languages.update(new_codes)


def _lexeme_row(lexeme: Lexeme) -> tuple[object, ...]:
    return (
        lexeme.lang_code,
        lexeme.headword,
        lexeme.gloss,
        lexeme.romanization,
        lexeme.pos,
        lexeme.is_reconstructed,
        lexeme.source_ref,
    )


def _upsert_lexemes(
    cursor: psycopg.Cursor, rows: list[tuple[object, ...]]
) -> list[int]:
    """Upsert lexemes, returning their ids in the same order as `rows`.

    Returns:
        The upserted ids, one per row, in `rows` order.

    Raises:
        RuntimeError: If any upsert returns no id.
    """
    cursor.executemany(_LEXEME_UPSERT_SQL, rows, returning=True)
    ids: list[int] = []
    while True:
        row = cursor.fetchone()
        if row is None:
            msg = "lexeme upsert returned no id"
            raise RuntimeError(msg)
        ids.append(row[0])
        if not cursor.nextset():
            break
    return ids
