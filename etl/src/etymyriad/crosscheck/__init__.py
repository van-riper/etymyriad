"""Check the ETL's edges against Wiktionary's own etymology trees."""

from etymyriad.crosscheck._compare import graph_index, missing_edges
from etymyriad.crosscheck._fetch import (
    edited_after_dump,
    extract_tree,
    fetch_tree,
)
from etymyriad.crosscheck._report import (
    headwords_by_language,
    tree_headwords,
)
from etymyriad.crosscheck._tree import TreeEdge, TreeNode, tree_edges

__all__ = [
    "TreeEdge",
    "TreeNode",
    "edited_after_dump",
    "extract_tree",
    "fetch_tree",
    "graph_index",
    "headwords_by_language",
    "missing_edges",
    "tree_edges",
    "tree_headwords",
]
