"""Upsert the etymology graph into Postgres.

Idempotent: re-running with the same data produces the same rows. Lexemes are
upserted on their natural key, edges on (src, dst, rel_type).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg

if TYPE_CHECKING:
    from collections.abc import Iterable

    from etymyriad.model import EtymEdge, Lexeme


def load_edges(database_url: str, edges: Iterable[EtymEdge]) -> int:
    """Upsert edges and their endpoint lexemes into Postgres.

    Idempotent: lexemes upsert on their natural key and edges on
    (src_id, dst_id, rel_type), so re-running the same input adds no
    duplicate rows.

    Args:
        database_url: Postgres connection string.
        edges: The etymology edges to load.

    Returns:
        The number of edges processed.
    """
    count = 0
    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        for edge in edges:
            src_id = _upsert_lexeme(cursor, edge.src)
            dst_id = _upsert_lexeme(cursor, edge.dst)
            _upsert_edge(cursor, src_id, dst_id, edge)
            count += 1
        connection.commit()

    return count


def _ensure_language(cursor: psycopg.Cursor, code: str) -> None:
    """Insert a bare language row if it does not exist yet."""
    cursor.execute(
        """
        INSERT INTO language (code, name)
        VALUES (%s, %s)
        ON CONFLICT (code) DO NOTHING
        """,
        (code, code),  # name backfilled later from a language table dump
    )


def _upsert_lexeme(cursor: psycopg.Cursor, lexeme: Lexeme) -> int:
    """Insert or fetch a lexeme.

    Args:
        cursor: An open database cursor.
        lexeme: The lexeme to upsert on its natural key.

    Returns:
        The id of the upserted lexeme.

    Raises:
        RuntimeError: If the upsert returns no id.
    """
    _ensure_language(cursor, lexeme.lang_code)
    cursor.execute(
        """
        INSERT INTO lexeme (lang_code, headword, gloss, romanization, pos,
                            is_reconstructed, source_ref)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (lang_code, headword, COALESCE(gloss, ''))
        DO UPDATE SET source_ref = EXCLUDED.source_ref
        RETURNING id
        """,
        (
            lexeme.lang_code,
            lexeme.headword,
            lexeme.gloss,
            lexeme.romanization,
            lexeme.pos,
            lexeme.is_reconstructed,
            lexeme.source_ref,
        ),
    )

    row = cursor.fetchone()
    if row is None:
        msg = "lexeme upsert returned no id"
        raise RuntimeError(msg)
    return row[0]


def _upsert_edge(
    cursor: psycopg.Cursor,
    src_id: int,
    dst_id: int,
    edge: EtymEdge,
) -> None:
    """Insert an edge, ignoring duplicates."""
    cursor.execute(
        """
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (src_id, dst_id, rel_type) DO NOTHING
        """,
        (src_id, dst_id, edge.rel_type.value, edge.source_ref),
    )
