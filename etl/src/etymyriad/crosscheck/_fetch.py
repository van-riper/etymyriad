"""Fetch a headword's etymology tree from the live Wiktionary page."""

from __future__ import annotations

import html
import json
import re
from typing import TYPE_CHECKING

from etymyriad.languages import USER_AGENT

if TYPE_CHECKING:
    import httpx

    from etymyriad.crosscheck._tree import TreeNode

_API_URL = "https://en.wiktionary.org/w/api.php"
_TREE_ATTRIBUTES = re.compile(
    r'data-lang="([^"]*)"[^>]*?data-ety-tree-json="([^"]*)"'
)


def extract_tree(page_html: str, lang_code: str) -> TreeNode | None:
    """Pull a language's first etymology tree out of a rendered page.

    The Wiktextract dump mangles this payload, so the rendered page is
    the intact copy.

    Args:
        page_html: The page's rendered HTML.
        lang_code: The language section whose tree to take.

    Returns:
        The decoded tree, or None if the page carries none.
    """
    for lang, payload in _TREE_ATTRIBUTES.findall(page_html):
        if lang == lang_code:
            return json.loads(html.unescape(payload))
    return None


def fetch_tree(
    client: httpx.Client, headword: str, lang_code: str
) -> TreeNode | None:
    """Fetch and extract one headword's tree from Wiktionary.

    Args:
        client: The HTTP client to use.
        headword: The English Wiktionary page title.
        lang_code: The language section whose tree to take.

    Returns:
        The decoded tree, or None if the page is missing or has none.
    """
    response = client.get(
        _API_URL,
        params={
            "action": "parse",
            "page": headword,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        },
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    body = response.json()
    if "parse" not in body:
        return None
    return extract_tree(body["parse"]["text"], lang_code)
