"""Check the ETL's edges against Wiktionary's own etymology trees."""

from __future__ import annotations

from etymyriad.crosscheck._compare import graph_index, missing_edges
from etymyriad.crosscheck._fetch import extract_tree, fetch_tree
from etymyriad.crosscheck._report import tree_headwords
from etymyriad.crosscheck._tree import TreeEdge, TreeNode, tree_edges

__all__ = [
    "TreeEdge",
    "TreeNode",
    "extract_tree",
    "fetch_tree",
    "graph_index",
    "missing_edges",
    "tree_edges",
    "tree_headwords",
]
