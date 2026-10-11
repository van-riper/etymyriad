"""Flatten a Wiktionary etymology tree into ancestor -> descendant edges."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping

type TreeNode = Mapping[str, Any]


class TreeEdge(NamedTuple):
    """One link of a Wiktionary etymology tree.

    Attributes:
        src_lang: The ancestor's Wiktionary language code.
        src_term: The ancestor's term as the tree shows it.
        dst_lang: The descendant's Wiktionary language code.
        dst_term: The descendant's term as the tree shows it.
        keyword: The tree's relation keyword, e.g. "inherited" or "affix".
    """

    src_lang: str
    src_term: str
    dst_lang: str
    dst_term: str
    keyword: str


def _term_of(node: TreeNode) -> str | None:
    """Return a node's term, or its `alt` form for an inline-only node.

    A node that names only a language (e.g. Pre-Greek) has neither.
    """
    return node.get("term") or node.get("alt")


def tree_edges(tree: TreeNode) -> set[TreeEdge]:
    """Flatten a tree node and everything above it into edges.

    A node's `children` are relations, each with a keyword and the
    ancestor nodes it names, so every ancestor-to-node link is already
    in the direction the graph stores.

    Args:
        tree: A node of the `data-ety-tree-json` payload, usually the root.

    Returns:
        One edge per ancestor named under each relation.
    """
    edges: set[TreeEdge] = set()
    term = _term_of(tree)
    if term is None:
        return edges
    for relation in tree.get("children", []):
        for ancestor in relation["terms"]:
            ancestor_term = _term_of(ancestor)
            if ancestor_term is None:
                continue
            edges.add(
                TreeEdge(
                    ancestor["lang"],
                    ancestor_term,
                    tree["lang"],
                    term,
                    relation["keyword"],
                )
            )
            edges |= tree_edges(ancestor)
    return edges
