"""Tests for the durable graph layout module."""

from __future__ import annotations

import psycopg

from etymyriad.layout import fetch_graph
from etymyriad.load import load_edges
from etymyriad.model import EtymEdge, Lexeme, RelType

_EDGE = EtymEdge(
    src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
    dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
    rel_type=RelType.INHERITED,
    source_ref="w:e",
)


def test_fetch_graph_maps_edges_to_lexeme_indices(db_url: str) -> None:
    """Each edge's (src, dst) indices point at the right lexeme_ids."""
    load_edges(db_url, [_EDGE])
    with psycopg.connect(db_url) as conn:
        src_id, dst_id = conn.execute(
            "SELECT src_id, dst_id FROM etymology"
        ).fetchone()

    lexeme_ids, edges = fetch_graph(db_url)

    assert len(edges) == 1
    src_idx, dst_idx = edges[0]
    assert lexeme_ids[src_idx] == src_id
    assert lexeme_ids[dst_idx] == dst_id


def test_fetch_graph_includes_isolated_lexeme_with_no_edges(
    db_url: str,
) -> None:
    """A lexeme with no etymology rows still appears in the result."""
    load_edges(db_url, [_EDGE])
    with psycopg.connect(db_url) as conn:
        conn.execute(
            "INSERT INTO language (code, name) VALUES ('en', 'English')"
        )
        row = conn.execute(
            "INSERT INTO lexeme (lang_code, headword, source_ref) "
            "VALUES ('en', 'isolated', 'w:iso') RETURNING id"
        ).fetchone()
        conn.commit()
    isolated_id = row[0]

    lexeme_ids, edges = fetch_graph(db_url)

    assert isolated_id in lexeme_ids
    isolated_index = lexeme_ids.index(isolated_id)
    assert all(isolated_index not in pair for pair in edges)
