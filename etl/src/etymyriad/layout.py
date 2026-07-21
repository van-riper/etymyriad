"""Compute and persist a durable, whole-graph lexeme layout.

Positions are computed once, offline, over the full lexeme/etymology
graph and stored in `lexeme_layout` -- unlike the client's per-request
ring layout (web/src/lib/graph.ts), every ego-network fetch touching a
node returns the same coordinates for it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import psycopg

if TYPE_CHECKING:
    from uuid import UUID

_log = logging.getLogger(__name__)


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
