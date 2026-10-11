"""Tests for flattening a Wiktionary etymology tree into edges."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etymyriad.crosscheck import TreeEdge, TreeNode, tree_edges

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(headword: str) -> TreeNode:
    return json.loads((_FIXTURES / f"{headword}.json").read_text("utf-8"))


def test_wine_flattens_to_ancestor_to_descendant_edges() -> None:
    """Every link of a real tree comes out ancestor to descendant."""
    assert tree_edges(_load("wine")) == {
        TreeEdge("enm", "wyn", "en", "wine", "inherited"),
        TreeEdge("ang", "wīn", "enm", "wyn", "inherited"),
        TreeEdge("gmw-pro", "*wīn", "ang", "wīn", "inherited"),
        TreeEdge("gem-pro", "*wīną", "gmw-pro", "*wīn", "inherited"),
        TreeEdge("la", "vīnum", "gem-pro", "*wīną", "bor"),
        TreeEdge("itc-pro", "*wīnom", "la", "vīnum", "inherited"),
        TreeEdge("ine-pro", "*wéyh₁ō", "itc-pro", "*wīnom", "derived"),
        TreeEdge("ine-pro", "*weh₁y-", "ine-pro", "*wéyh₁ō", "affix"),
        TreeEdge("ine-pro", "*-ō", "ine-pro", "*wéyh₁ō", "affix"),
    }


@pytest.mark.parametrize("headword", ["winemerchant", "incomprehensibleness"])
def test_compound_tree_joins_both_branches(headword: str) -> None:
    """A compound's root has an edge from each merged branch."""
    edges = tree_edges(_load(headword))
    root_edges = [edge for edge in edges if edge.dst_term == headword]
    assert len(root_edges) >= 2


def test_inline_only_node_uses_its_alt_form() -> None:
    """A node with only `alt` still yields edges under that form."""
    edges = tree_edges(_load("merchant"))
    assert TreeEdge("itc-pro", "*-ājō", "itc-pro", "*-āō", "from") in edges
