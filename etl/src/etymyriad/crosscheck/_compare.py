"""Diff a flattened Wiktionary tree against the ETL's edges."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from etymyriad.model import EtymEdge
from etymyriad.normalize import referenced_term_key

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from etymyriad.crosscheck._tree import TreeEdge
    from etymyriad.model import Term

type NodeKey = tuple[str, str]
type GraphIndex = Mapping[NodeKey, set[NodeKey]]


def graph_index(items: Iterable[EtymEdge | Term]) -> GraphIndex:
    """Index edges by descendant so each lookup is one dict hit.

    Args:
        items: The ETL's edges, and any lone terms (ignored).

    Returns:
        Each descendant's node key mapped to its ancestors' node keys.
    """
    index: defaultdict[NodeKey, set[NodeKey]] = defaultdict(set)
    for item in items:
        if isinstance(item, EtymEdge):
            index[item.dst.key].add(item.src.key)
    return index


def missing_edges(
    tree: Iterable[TreeEdge], index: GraphIndex
) -> list[TreeEdge]:
    """List the tree edges the graph does not have.

    Args:
        tree: A flattened Wiktionary tree.
        index: The ETL's edges from `graph_index`.

    Returns:
        Each tree edge whose ancestor is not among the descendant's
        ancestors in the graph, in sorted order.
    """
    return sorted(
        edge
        for edge in tree
        if referenced_term_key(edge.src_lang, edge.src_term)
        not in index.get(referenced_term_key(edge.dst_lang, edge.dst_term), ())
    )
