"""Fetch a headword's etymology tree from Wiktionary's rendered page."""

from __future__ import annotations

import html
import json
import re
from typing import TYPE_CHECKING, Any

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


def _api_get(client: httpx.Client, params: dict[str, str]) -> dict[str, Any]:
    """Call the Wiktionary API and decode its JSON body.

    Args:
        client: The HTTP client to use.
        params: The query parameters, minus the format ones.

    Returns:
        The decoded response body.
    """
    response = client.get(
        _API_URL,
        params={**params, "format": "json", "formatversion": "2"},
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return response.json()


def _revision_as_of(
    client: httpx.Client, headword: str, dump_date: str
) -> int | None:
    """Find the page's last revision on or before the dump date.

    Args:
        client: The HTTP client to use.
        headword: The English Wiktionary page title.
        dump_date: The dump's date, as YYYY-MM-DD.

    Returns:
        The revision id, or None if the page did not exist by then.
    """
    body = _api_get(
        client,
        {
            "action": "query",
            "prop": "revisions",
            "titles": headword,
            "rvlimit": "1",
            "rvdir": "older",
            "rvstart": f"{dump_date}T23:59:59Z",
            "rvprop": "ids",
        },
    )
    revisions = body["query"]["pages"][0].get("revisions") or []
    return revisions[0]["revid"] if revisions else None


def fetch_tree(
    client: httpx.Client, headword: str, lang_code: str, dump_date: str
) -> TreeNode | None:
    """Fetch one headword's tree as the page stood on the dump date.

    Pinning the revision keeps a later edit to the page from reading as a
    parser miss. The revision still renders with today's modules and
    ancestor pages, so edits elsewhere can still show.

    Args:
        client: The HTTP client to use.
        headword: The English Wiktionary page title.
        lang_code: The language section whose tree to take.
        dump_date: The dump's date, as YYYY-MM-DD.

    Returns:
        The decoded tree, or None if the page did not exist by the dump
        date or has no tree for that language.
    """
    revision = _revision_as_of(client, headword, dump_date)
    if revision is None:
        return None
    body = _api_get(
        client, {"action": "parse", "oldid": str(revision), "prop": "text"}
    )
    if "parse" not in body:
        return None
    return extract_tree(body["parse"]["text"], lang_code)
