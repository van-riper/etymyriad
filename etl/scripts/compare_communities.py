#!/usr/bin/env python3
"""Spike: structural communities vs. language-family grouping.

Question: does Louvain community detection on pure topology (no
attribute data) mostly agree with the `language.lang_family` labels
already in the graph, or does it diverge in a way that's itself
etymologically meaningful (e.g. heavy borrowing)?

Usage: `./etl/scripts/compare_communities.py`
"""

from __future__ import annotations

import logging
from collections import Counter

import igraph
import psycopg

from etymyriad.config import Config
from etymyriad.layout import fetch_graph

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_log = logging.getLogger(__name__)

_MIN_LANGUAGE_LEXEMES = 500  # ignore tiny/proto languages as noise


def fetch_lang_families(database_url: str, lexeme_ids: list) -> list[str]:
    """Return one lang_family label per lexeme_id, in the same order."""
    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT l.id, COALESCE(lang.lang_family, 'unknown') "
            "FROM lexeme l JOIN language lang ON lang.code = l.lang_code"
        )
        family_by_id = dict(cursor.fetchall())
    return [family_by_id[lid] for lid in lexeme_ids]


def community_family_composition(
    communities: list[int], families: list[str]
) -> dict[int, Counter]:
    """Tally each community's members by family label.

    Returns:
        Community id -> a Counter of its members' family labels.
    """
    composition: dict[int, Counter] = {}
    for community, family in zip(communities, families, strict=True):
        composition.setdefault(community, Counter())[family] += 1
    return composition


def large_communities(
    composition: dict[int, Counter], min_members: int
) -> dict[int, Counter]:
    """Keep only communities with at least min_members members.

    Returns:
        The subset of composition meeting the size threshold.
    """
    return {
        cid: counts
        for cid, counts in composition.items()
        if sum(counts.values()) >= min_members
    }


def weighted_purity(large: dict[int, Counter]) -> float:
    """Fraction of members sharing their community's plurality family.

    Returns:
        A value in [0, 1], size-weighted across all of `large`.
    """
    total = sum(sum(counts.values()) for counts in large.values())
    if total == 0:
        return 0.0
    dominant = sum(counts.most_common(1)[0][1] for counts in large.values())
    return dominant / total


def print_size_buckets(sizes: list[int]) -> None:
    """Print how many components fall into size buckets, and coverage."""
    bounds = [(1, 1), (2, 9), (10, 99), (100, 999), (1000, None)]
    for low, high in bounds:
        in_bucket = [
            s for s in sizes if s >= low and (high is None or s <= high)
        ]
        label = f"{low}+" if high is None else f"{low}-{high}"
        print(
            f"  size {label:8s} {len(in_bucket):7d} components, "
            f"{sum(in_bucket):9d} lexemes"
        )


def print_largest_communities(
    large: dict[int, Counter], top_n: int = 15
) -> None:
    """Print the top_n largest communities and their family breakdown."""
    print("\nLargest communities and their family composition:")
    by_size = sorted(large.items(), key=lambda kv: -sum(kv[1].values()))
    for cid, counts in by_size[:top_n]:
        total = sum(counts.values())
        breakdown = ", ".join(f"{f}={n}" for f, n in counts.most_common(3))
        print(f"  community {cid:6d} n={total:6d}  {breakdown}")


def print_mixed_communities(
    large: dict[int, Counter], purity_threshold: float = 0.6
) -> None:
    """Print large communities where no family holds a majority."""
    mixed = {
        cid: counts
        for cid, counts in large.items()
        if counts.most_common(1)[0][1] / sum(counts.values()) < purity_threshold
    }
    print(
        f"\n{len(mixed)} of {len(large)} large communities are 'mixed' "
        f"(plurality family < {purity_threshold:.0%} of members) -- "
        "candidate cross-family borrowing/loanword clusters:"
    )
    by_size = sorted(mixed.items(), key=lambda kv: -sum(kv[1].values()))
    for cid, counts in by_size:
        total = sum(counts.values())
        breakdown = ", ".join(f"{f}={n}" for f, n in counts.most_common(4))
        print(f"  community {cid:6d} n={total:6d}  {breakdown}")


def main() -> int:
    """Compare Louvain communities against language-family labels.

    Returns:
        0 on success (the process exit code).
    """
    config = Config.from_env()
    _log.info("fetching graph + language labels")
    lexeme_ids, edges = fetch_graph(config.database_url)
    families = fetch_lang_families(config.database_url, lexeme_ids)

    _log.info("building undirected graph and detecting communities")
    graph = igraph.Graph(n=len(lexeme_ids), edges=edges, directed=False)
    components = graph.connected_components()
    communities = list(graph.community_multilevel().membership)
    _log.info(
        "%d connected components, %d Louvain communities",
        len(components),
        len(set(communities)),
    )

    print("\nConnected-component size distribution:")
    print_size_buckets(list(components.sizes()))

    family_ids = {f: i for i, f in enumerate(sorted(set(families)))}
    nmi = igraph.compare_communities(
        communities, [family_ids[f] for f in families], method="nmi"
    )
    print(f"\nNMI(community, lang_family) = {nmi:.4f}")

    composition = community_family_composition(communities, families)
    large = large_communities(composition, _MIN_LANGUAGE_LEXEMES)
    total_large = sum(sum(counts.values()) for counts in large.values())
    print(
        f"\n{len(large)} communities have >= {_MIN_LANGUAGE_LEXEMES} "
        f"members, covering {total_large} of {len(lexeme_ids)} lexemes "
        f"({100 * total_large / len(lexeme_ids):.1f}%)."
    )
    print(
        "Size-weighted purity over those large communities (fraction "
        "whose family matches their community's plurality family) = "
        f"{weighted_purity(large):.3f}"
    )
    print_largest_communities(large)
    print_mixed_communities(large)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
