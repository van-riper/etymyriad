"""Tests for diffing a flattened tree against the ETL's edges."""

from __future__ import annotations

from etymyriad.crosscheck import TreeEdge, graph_index, missing_edges
from etymyriad.model import EtymEdge, RelType, Term


def _edge(src: Term, dst: Term, rel_type: RelType) -> EtymEdge:
    return EtymEdge(src=src, dst=dst, rel_type=rel_type, anchor="a")


_WINE = Term("en", "wine")
_WYN = Term("enm", "wyn")
_WIN = Term("ang", "wīn")


def test_edge_in_the_graph_is_not_missing() -> None:
    """A tree edge the ETL also produced is not reported."""
    index = graph_index([_edge(_WYN, _WINE, RelType.INHERITED)])
    tree = {TreeEdge("enm", "wyn", "en", "wine", "inherited")}
    assert missing_edges(tree, index) == []


def test_absent_edge_is_reported() -> None:
    """A tree edge with no counterpart in the graph is reported."""
    index = graph_index([_edge(_WYN, _WINE, RelType.INHERITED)])
    absent = TreeEdge("ang", "wīn", "enm", "wyn", "inherited")
    assert missing_edges({absent}, index) == [absent]


def test_starred_tree_term_matches_the_stored_headword() -> None:
    """The graph stores proto headwords without the star."""
    proto = Term("gem-pro", "wīną", is_reconstructed=True)
    index = graph_index([_edge(proto, _WIN, RelType.INHERITED)])
    tree = {TreeEdge("gem-pro", "*wīną", "ang", "wīn", "inherited")}
    assert missing_edges(tree, index) == []


def test_lone_term_adds_no_edge() -> None:
    """An entry with no edges of its own contributes nothing."""
    index = graph_index([_WINE])
    tree = {TreeEdge("enm", "wyn", "en", "wine", "inherited")}
    assert missing_edges(tree, index) == [*tree]


def test_macron_in_the_tree_matches_the_plain_stored_headword() -> None:
    """Wiktionary titles drop macrons the tree displays."""
    index = graph_index([_edge(Term("ang", "win"), _WYN, RelType.INHERITED)])
    tree = {TreeEdge("ang", "wīn", "enm", "wyn", "inherited")}
    assert missing_edges(tree, index) == []
