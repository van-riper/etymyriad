#!/usr/bin/env python3
"""ETYM-80 spike: does a statistical backbone filter fit this graph?

Question: which backbone/sparsification filter (Disparity Filter, Polya
Urn, Marginal Likelihood, Noise Corrected, ECM, GloSS, LANS) keeps
etymologically meaningful edges and drops redundant/speculative ones on
etymyriad's real edge set?

Usage: `./etl/scripts/backbone_filter.py`
"""

from __future__ import annotations

import logging
from collections import Counter
from itertools import pairwise

import psycopg

from etymyriad.config import Config
from etymyriad.layout import compute_degree, fetch_graph

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_log = logging.getLogger(__name__)

_KNOWN_CHAIN = [
    ("ἐτυμολογία", "grc"),
    ("etymologia", "la"),
    ("etymology", "en"),
]


def disparity_alpha(degree: int) -> float:
    """Disparity filter significance for a node's own edges.

    Every one of these filters (Disparity, Polya Urn, Marginal
    Likelihood, Noise Corrected, ECM, GloSS, LANS) needs a real edge
    weight to compute a null-model p-value; etymyriad's etymology
    table has none (db/schema.sql: src_id, dst_id, rel_type,
    source_ref only -- every edge is a single sourced claim, not an
    aggregated count). Assuming the closest available stand-in,
    uniform weight 1 on every edge, collapses the disparity filter's
    formula to a pure function of degree, so it's used here to
    measure exactly how much that degeneracy costs.

    Args:
        degree: The node's total (in + out) edge count.

    Returns:
        The alpha value in [0, 1]; 0.0 for degree <= 1 (an edge with
        no sibling edges is trivially significant).
    """
    if degree <= 1:
        return 0.0
    return (1 - 1 / degree) ** (degree - 1)


def edge_alphas(
    degrees: list[int], edges: list[tuple[int, int]]
) -> list[float]:
    """Per-edge disparity alpha, keeping an edge if either end is significant.

    Args:
        degrees: One degree count per vertex index.
        edges: (src_index, dst_index) pairs into the vertex range.

    Returns:
        One alpha per edge, the minimum of its two endpoints' alphas.
    """
    return [
        min(disparity_alpha(degrees[src]), disparity_alpha(degrees[dst]))
        for src, dst in edges
    ]


def fraction_kept(alphas: list[float], threshold: float) -> float:
    """Fraction of edges whose alpha is significant at a threshold.

    Returns:
        A value in [0, 1].
    """
    kept = sum(1 for alpha in alphas if alpha < threshold)
    return kept / len(alphas) if alphas else 0.0


def same_source_alpha_spread(
    degrees: list[int], edges: list[tuple[int, int]]
) -> tuple[int, int]:
    """Check whether a node's own edges ever get distinct alpha values.

    Returns:
        (nodes_checked, nodes_with_more_than_one_distinct_alpha) --
        the second should be 0, since alpha depends only on the
        source node's degree, never on which edge it is.
    """
    alphas_by_source: dict[int, set[float]] = {}
    for (src, _dst), alpha in zip(
        edges, (disparity_alpha(degrees[s]) for s, _ in edges), strict=True
    ):
        alphas_by_source.setdefault(src, set()).add(alpha)
    multi_degree_sources = {
        src: alphas
        for src, alphas in alphas_by_source.items()
        if degrees[src] > 2
    }
    distinct = sum(
        1 for alphas in multi_degree_sources.values() if len(alphas) > 1
    )
    return len(multi_degree_sources), distinct


def fetch_rel_type_counts(database_url: str) -> Counter:
    """Tally etymology rows by rel_type.

    Returns:
        A Counter mapping each etym_rel_type value to its row count.
    """
    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT rel_type, count(*) FROM etymology GROUP BY rel_type"
        )
        return Counter(dict(cursor.fetchall()))


def fetch_chain_edges(
    database_url: str, chain: list[tuple[str, str]]
) -> list[tuple[str, str, str, int, int]]:
    """Look up rel_type and degree for each consecutive pair in a chain.

    Args:
        database_url: Postgres connection string.
        chain: (headword, lang_code) pairs, ancestor to descendant.

    Returns:
        One (src_headword, dst_headword, rel_type, src_degree,
        dst_degree) row per consecutive pair that has a direct edge.
    """
    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        rows = []
        for (src_word, src_lang), (dst_word, dst_lang) in pairwise(chain):
            cursor.execute(
                """
                SELECT e.rel_type, s.degree, d.degree
                FROM etymology e
                JOIN lexeme src ON src.id = e.src_id
                JOIN lexeme dst ON dst.id = e.dst_id
                JOIN lexeme_layout s ON s.lexeme_id = src.id
                JOIN lexeme_layout d ON d.lexeme_id = dst.id
                WHERE src.headword = %s AND src.lang_code = %s
                  AND dst.headword = %s AND dst.lang_code = %s
                """,
                (src_word, src_lang, dst_word, dst_lang),
            )
            for rel_type, src_degree, dst_degree in cursor.fetchall():
                rows.append((
                    src_word,
                    dst_word,
                    rel_type,
                    src_degree,
                    dst_degree,
                ))
    return rows


def main() -> int:
    """Measure the disparity filter's behavior on the real etymology graph.

    Returns:
        0 on success (the process exit code).
    """
    config = Config.from_env()
    _log.info("fetching graph")
    lexeme_ids, edges = fetch_graph(config.database_url)
    degrees = compute_degree(len(lexeme_ids), edges)
    alphas = edge_alphas(degrees, edges)

    print(f"\n{len(edges)} edges, {len(lexeme_ids)} lexemes")
    for threshold in (0.05, 0.10):
        kept = fraction_kept(alphas, threshold)
        print(
            f"disparity filter alpha < {threshold:.2f}: keeps "
            f"{kept:.1%} of edges ({round(kept * len(edges)):,} of "
            f"{len(edges):,})"
        )

    checked, distinct = same_source_alpha_spread(degrees, edges)
    print(
        f"\n{checked} source nodes have degree > 2; {distinct} of them "
        "produce more than one distinct alpha across their own outgoing "
        "edges (expected 0 -- alpha is a pure function of degree, so it "
        "cannot rank one edge above a sibling from the same node)."
    )

    print("\nrel_type distribution (all 2.99M edges):")
    for rel_type, count in fetch_rel_type_counts(
        config.database_url
    ).most_common():
        print(f"  {rel_type:24s} {count:9,d}")

    print(f"\nSpot-check: known chain {_KNOWN_CHAIN}")
    for src, dst, rel_type, src_degree, dst_degree in fetch_chain_edges(
        config.database_url, _KNOWN_CHAIN
    ):
        alpha = min(disparity_alpha(src_degree), disparity_alpha(dst_degree))
        print(
            f"  {src} -> {dst}  rel_type={rel_type}  "
            f"src_degree={src_degree} dst_degree={dst_degree}  "
            f"alpha={alpha:.4f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
