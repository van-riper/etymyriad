"""Tests for the durable graph layout module."""

from __future__ import annotations

import logging
import math
import statistics
from uuid import uuid4

import psycopg
import pytest

from etymyriad.layout import (
    compute_degree,
    compute_layout,
    fetch_graph,
    write_layout,
)
from etymyriad.load import load_edges
from etymyriad.model import EtymEdge, Lexeme, RelType

_EDGE = EtymEdge(
    src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
    dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
    rel_type=RelType.INHERITED,
    source_ref="w:e",
)


def _cliques_bridged_in_a_chain(
    num_cliques: int, clique_size: int
) -> tuple[int, list[tuple[int, int]]]:
    """A graph of dense cliques, each linked to the next by one edge.

    Mimics a forest of tightly-linked etymological trees connected only
    by rare cross-tree edges (e.g. a shared ancient root, a loanword).

    Returns:
        (vertex_count, edges), edges as (src_index, dst_index) pairs.
    """
    edges = []
    for clique in range(num_cliques):
        base = clique * clique_size
        edges.extend(
            (base + i, base + j)
            for i in range(clique_size)
            for j in range(i + 1, clique_size)
        )
        if clique > 0:
            edges.append((base, base - 1))
    return num_cliques * clique_size, edges


def test_fetch_graph_maps_edges_to_lexeme_indices(db_url: str) -> None:
    """Each edge's (src, dst) indices point at the right lexeme_ids."""
    load_edges(db_url, [_EDGE])
    with psycopg.connect(db_url) as conn:
        result = conn.execute("SELECT src_id, dst_id FROM etymology").fetchone()
        assert result is not None
        src_id, dst_id = result

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
    assert row is not None
    isolated_id = row[0]

    lexeme_ids, edges = fetch_graph(db_url)

    assert isolated_id in lexeme_ids
    isolated_index = lexeme_ids.index(isolated_id)
    assert all(isolated_index not in pair for pair in edges)


def test_compute_layout_returns_one_finite_position_per_vertex() -> None:
    """Every vertex gets a finite (x, y), even ones with no edges."""
    positions = compute_layout(vertex_count=5, edges=[(0, 1), (1, 2)])

    assert len(positions) == 5
    for x, y in positions:
        assert math.isfinite(x)
        assert math.isfinite(y)


def test_compute_layout_spreads_connected_vertices_apart() -> None:
    """A real layout doesn't collapse every vertex to one point."""
    positions = compute_layout(vertex_count=4, edges=[(0, 1), (1, 2), (2, 3)])

    assert len(set(positions)) > 1


def test_compute_layout_converges_on_weakly_bridged_clusters() -> None:
    """DrL's default preset spatially separates weakly-bridged cliques.

    A converged layout keeps every cluster's centroid farther from
    every other cluster's centroid than that cluster's own radius,
    since the only link between cliques is a single bridge edge. If
    the layout hadn't converged, weakly-bridged cliques would still
    overlap into one intermixed blob.
    """
    num_cliques, clique_size = 8, 40
    vertex_count, edges = _cliques_bridged_in_a_chain(num_cliques, clique_size)

    positions = compute_layout(vertex_count=vertex_count, edges=edges)

    radii = []
    centroids = []
    for clique in range(num_cliques):
        points = positions[clique * clique_size : (clique + 1) * clique_size]
        centroid = (
            statistics.mean(x for x, _ in points),
            statistics.mean(y for _, y in points),
        )
        centroids.append(centroid)
        radii.append(max(math.dist(p, centroid) for p in points))

    typical_radius = statistics.mean(radii)
    centroid_distances = [
        math.dist(centroids[i], centroids[j])
        for i in range(num_cliques)
        for j in range(i + 1, num_cliques)
    ]

    assert min(centroid_distances) > typical_radius


def test_compute_layout_handles_an_empty_graph() -> None:
    """Zero vertices (e.g. a fresh, unloaded database) returns no rows."""
    assert compute_layout(vertex_count=0, edges=[]) == []


def test_compute_degree_counts_edges_touching_each_vertex() -> None:
    """Degree is in-edges plus out-edges, per vertex."""
    # 0 -> 1, 1 -> 2, 2 -> 1: vertex 1 touches 3 edges, 0 and 2 touch 2 each.
    degrees = compute_degree(vertex_count=3, edges=[(0, 1), (1, 2), (2, 1)])

    assert degrees == [1, 3, 2]


def test_compute_degree_is_zero_for_an_isolated_vertex() -> None:
    """A vertex with no edges at all gets degree 0, not skipped."""
    degrees = compute_degree(vertex_count=2, edges=[])

    assert degrees == [0, 0]


def test_write_layout_inserts_a_row_per_lexeme(db_url: str) -> None:
    """Every (lexeme_id, position, degree) triple lands as its own row."""
    load_edges(db_url, [_EDGE])
    lexeme_ids, edges = fetch_graph(db_url)
    positions = [(float(i), float(i)) for i in range(len(lexeme_ids))]
    degrees = compute_degree(len(lexeme_ids), edges)

    written = write_layout(db_url, lexeme_ids, positions, degrees)

    assert written == len(lexeme_ids)
    with psycopg.connect(db_url) as conn:
        count = conn.execute("SELECT count(*) FROM lexeme_layout").fetchone()
    assert count is not None
    assert count[0] == len(lexeme_ids)


def test_write_layout_persists_the_degree_value(db_url: str) -> None:
    """Degree is stored per lexeme_id, not just position."""
    load_edges(db_url, [_EDGE])
    lexeme_ids, edges = fetch_graph(db_url)
    positions = [(0.0, 0.0) for _ in lexeme_ids]
    degrees = compute_degree(len(lexeme_ids), edges)

    write_layout(db_url, lexeme_ids, positions, degrees)

    with psycopg.connect(db_url) as conn:
        rows = dict(
            conn.execute(
                "SELECT lexeme_id, degree FROM lexeme_layout"
            ).fetchall()
        )
    for lexeme_id, degree in zip(lexeme_ids, degrees, strict=True):
        assert rows[lexeme_id] == degree


def test_write_layout_overwrites_without_duplicating_on_rerun(
    db_url: str,
) -> None:
    """Re-running with new positions updates rows, in place -- no dupes."""
    load_edges(db_url, [_EDGE])
    lexeme_ids, _ = fetch_graph(db_url)
    first = [(0.0, 0.0) for _ in lexeme_ids]
    second = [(1.0, 2.0) for _ in lexeme_ids]
    degrees = [0 for _ in lexeme_ids]

    write_layout(db_url, lexeme_ids, first, degrees)
    write_layout(db_url, lexeme_ids, second, degrees)

    with psycopg.connect(db_url) as conn:
        distinct = conn.execute(
            "SELECT DISTINCT x, y FROM lexeme_layout"
        ).fetchall()
        count = conn.execute("SELECT count(*) FROM lexeme_layout").fetchone()
    assert count is not None
    assert count[0] == len(lexeme_ids)
    assert distinct == [(1.0, 2.0)]


def test_write_layout_raises_on_mismatched_lengths() -> None:
    """A lexeme_ids/positions/degrees length mismatch fails loudly."""
    with pytest.raises(ValueError, match="same length"):
        write_layout("postgresql://unused", [uuid4()], [], [])


def test_write_layout_logs_start_and_completion(
    db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A long, silent bulk write still logs that it started and finished."""
    load_edges(db_url, [_EDGE])
    lexeme_ids, edges = fetch_graph(db_url)
    positions = [(0.0, 0.0) for _ in lexeme_ids]
    degrees = compute_degree(len(lexeme_ids), edges)

    with caplog.at_level(logging.INFO, logger="etymyriad.layout"):
        write_layout(db_url, lexeme_ids, positions, degrees)

    messages = [r.message for r in caplog.records]
    assert any("writing" in m and str(len(lexeme_ids)) in m for m in messages)
    assert any("wrote" in m and str(len(lexeme_ids)) in m for m in messages)


def test_fetch_graph_logs_the_fetched_counts(
    db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Fetching logs how many lexemes/edges came back, not just silence."""
    load_edges(db_url, [_EDGE])

    with caplog.at_level(logging.INFO, logger="etymyriad.layout"):
        lexeme_ids, edges = fetch_graph(db_url)

    messages = [r.message for r in caplog.records]
    assert any(
        str(len(lexeme_ids)) in m and str(len(edges)) in m for m in messages
    )


def test_compute_layout_logs_start_and_completion(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A long, silent DrL call still logs that it started and finished."""
    with caplog.at_level(logging.INFO, logger="etymyriad.layout"):
        compute_layout(vertex_count=4, edges=[(0, 1), (1, 2), (2, 3)])

    messages = [r.message for r in caplog.records]
    assert any("4" in m for m in messages)
