"""Diff a flattened Wiktionary tree against the ETL's edges."""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from typing import TYPE_CHECKING

from etymyriad.model import EtymEdge
from etymyriad.normalize import referenced_term_key

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from etymyriad.crosscheck._tree import TreeEdge
    from etymyriad.model import GraphItem

type NodeKey = tuple[str, str]
type GraphIndex = Mapping[NodeKey, set[NodeKey]]


# shortcut: folds every language, so a real diacritic bug is hidden too;
# split the comparison per language if that starts to matter.
def _folded(key: NodeKey) -> NodeKey:
    """Drop combining marks from a key's headword.

    Wiktionary page titles omit macrons its trees display, so exact keys
    would report a lost edge where the graph only spells the term plainly.

    Args:
        key: A node key.

    Returns:
        The key with its headword's combining marks removed.
    """
    lang_code, headword = key
    decomposed = unicodedata.normalize("NFD", headword)
    return lang_code, "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )


def graph_index(items: Iterable[GraphItem]) -> GraphIndex:
    """Index edges by descendant so each lookup is one dict hit.

    Args:
        items: The ETL's edges, plus lone terms and section claims
            (ignored).

    Returns:
        Each descendant's node key mapped to its ancestors' node keys.
    """
    index: defaultdict[NodeKey, set[NodeKey]] = defaultdict(set)
    for item in items:
        if isinstance(item, EtymEdge):
            index[_folded(item.dst.key)].add(_folded(item.src.key))
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
        if _folded(referenced_term_key(edge.src_lang, edge.src_term))
        not in index.get(
            _folded(referenced_term_key(edge.dst_lang, edge.dst_term)), ()
        )
    )
