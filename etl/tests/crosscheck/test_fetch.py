"""Tests for pulling the tree JSON out of a rendered Wiktionary page."""

from __future__ import annotations

from etymyriad.crosscheck import extract_tree

_ONE_TREE = (
    '<ul class="etymonid" data-lang="{lang}" data-title="x" '
    'data-ety-tree-json="&#123; &quot;term&quot; : &quot;{term}&quot; '
    '&#125;">'
)


def test_extracts_the_escaped_tree_attribute() -> None:
    """The attribute is HTML-escaped JSON; it comes back decoded."""
    page = (
        '<ul class="etymonid" data-lang="en" data-title="wine" '
        'data-ety-tree-json="&#123; &quot;lang&quot; : &quot;en&quot;, '
        "&quot;term&quot; : &quot;wine&quot;, &quot;children&quot; : "
        '&#91; &#93; &#125;">'
    )
    assert extract_tree(page, "en") == {
        "lang": "en",
        "term": "wine",
        "children": [],
    }


def test_page_without_a_tree_returns_none() -> None:
    """Most pages carry no etymology tree."""
    assert extract_tree("<p>no tree here</p>", "en") is None


def test_tree_of_another_language_is_skipped() -> None:
    """A page lists one tree per language section; take the asked one."""
    page = _ONE_TREE.format(lang="de", term="de") + _ONE_TREE.format(
        lang="en", term="en"
    )
    assert extract_tree(page, "en") == {"term": "en"}


def test_first_tree_of_the_language_wins() -> None:
    """A language with several etymologies yields the first tree."""
    page = _ONE_TREE.format(lang="en", term="one") + _ONE_TREE.format(
        lang="en", term="two"
    )
    assert extract_tree(page, "en") == {"term": "one"}
