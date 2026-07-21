"""Compute and persist a durable, whole-graph lexeme layout.

Positions are computed once, offline, over the full lexeme/etymology
graph and stored in `lexeme_layout` -- unlike the client's per-request
ring layout (web/src/lib/graph.ts), every ego-network fetch touching a
node returns the same coordinates for it.
"""

from __future__ import annotations

import logging
from itertools import islice
from typing import TYPE_CHECKING

import igraph
import psycopg

if TYPE_CHECKING:
    from collections.abc import Iterator
    from uuid import UUID

_log = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 1000

_LEXEME_LAYOUT_UPSERT_SQL = """
    INSERT INTO lexeme_layout (lexeme_id, x, y, computed_at)
    VALUES (%s, %s, %s, now())
    ON CONFLICT (lexeme_id) DO UPDATE SET
        x = EXCLUDED.x, y = EXCLUDED.y, computed_at = EXCLUDED.computed_at
"""


def fetch_graph(
    database_url: str,
) -> tuple[list[UUID], list[tuple[int, int]]]:
    """Read the full lexeme/etymology graph as igraph-ready indices.

    Args:
        database_url: Postgres connection string.

    Returns:
        A (lexeme_ids, edges) pair: lexeme_ids is every lexeme's UUID,
        in a stable order; edges is every etymology edge as a
        (src_index, dst_index) pair into that same list. A lexeme with
        no etymology rows at all still appears in lexeme_ids.
    """
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM lexeme ORDER BY id")
        lexeme_ids = [row[0] for row in cur.fetchall()]

        index_by_id = {lexeme_id: i for i, lexeme_id in enumerate(lexeme_ids)}

        cur.execute("SELECT src_id, dst_id FROM etymology")
        edges = [
            (index_by_id[src], index_by_id[dst]) for src, dst in cur.fetchall()
        ]
    return lexeme_ids, edges


def compute_layout(
    vertex_count: int, edges: list[tuple[int, int]]
) -> list[tuple[float, float]]:
    """Lay out a graph with igraph's DrL algorithm.

    DrL (Distributed Recursive Layout) is built for million-node
    graphs, unlike a general force-directed layout (e.g.
    Fruchterman-Reingold), which doesn't scale past a few thousand
    nodes in reasonable time.

    Args:
        vertex_count: Total number of vertices (lexemes) to lay out.
        edges: (src_index, dst_index) pairs into the vertex range.

    Returns:
        One (x, y) position per vertex, in vertex-index order. Empty
        if vertex_count is 0.
    """
    if vertex_count == 0:
        return []
    graph = igraph.Graph(n=vertex_count, edges=edges, directed=True)
    layout = graph.layout_drl()
    return [(float(coord[0]), float(coord[1])) for coord in layout]


def write_layout(
    database_url: str,
    lexeme_ids: list[UUID],
    positions: list[tuple[float, float]],
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> int:
    """Upsert lexeme positions into `lexeme_layout`.

    Idempotent: re-running with the same lexeme_ids overwrites the
    existing rows in place (ON CONFLICT on the lexeme_id primary key)
    rather than duplicating them.

    Args:
        database_url: Postgres connection string.
        lexeme_ids: Every lexeme's UUID, matching `positions` 1:1.
        positions: One (x, y) pair per lexeme_id, in the same order.
        chunk_size: How many rows to batch and commit at a time.

    Returns:
        The number of rows written.

    Raises:
        ValueError: If lexeme_ids and positions differ in length.
    """
    if len(lexeme_ids) != len(positions):
        msg = (
            f"lexeme_ids ({len(lexeme_ids)}) and positions "
            f"({len(positions)}) must be the same length"
        )
        raise ValueError(msg)

    rows = (
        (lexeme_id, x, y)
        for lexeme_id, (x, y) in zip(lexeme_ids, positions, strict=True)
    )
    count = 0
    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        for chunk in _chunked(rows, chunk_size):
            cursor.executemany(_LEXEME_LAYOUT_UPSERT_SQL, chunk)
            connection.commit()
            count += len(chunk)
    return count


def _chunked(
    rows: Iterator[tuple[UUID, float, float]], size: int
) -> Iterator[list[tuple[UUID, float, float]]]:
    """Batch rows into chunks of a given size.

    Args:
        rows: Iterator of (lexeme_id, x, y) tuples.
        size: The number of rows per chunk.

    Yields:
        Lists of rows, each of size `size` or fewer for the final batch.
    """
    it = iter(rows)
    while batch := list(islice(it, size)):
        yield batch
