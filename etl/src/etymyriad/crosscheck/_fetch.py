"""Fetch a headword's etymology tree from Wiktionary's rendered page."""

import html
import json
import re
from typing import TYPE_CHECKING, Any

from etymyriad.config import USER_AGENT, WIKTIONARY_API_URL
from etymyriad.crosscheck._compare import _folded
from etymyriad.languages import resolve_language

if TYPE_CHECKING:
    import httpx

    from etymyriad.crosscheck._tree import TreeNode

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
        WIKTIONARY_API_URL,
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


def edited_after_dump(
    client: httpx.Client, lang_code: str, term: str, dump_date: str
) -> bool:
    """Tell whether a tree term's page changed on or after the dump date.

    A pinned revision still renders its ancestors from their current
    pages, so such an edit can add a tree edge the dump never had.

    Args:
        client: The HTTP client to use.
        lang_code: The term's Wiktionary language code.
        term: The term as the tree shows it.
        dump_date: The dump's date, as YYYY-MM-DD.

    Returns:
        True if the term's page, under its shown or mark-free spelling,
        was last edited on or after the dump date. False for a
        reconstruction in a language the registry does not know, since
        its page title cannot be built.
    """
    titles = {term, _folded((lang_code, term))[1]}
    if term.startswith("*"):
        language = resolve_language(lang_code)
        if language is None:
            return False
        titles = {
            f"Reconstruction:{language.name}/{title.removeprefix('*')}"
            for title in titles
        }
    body = _api_get(
        client,
        {
            "action": "query",
            "prop": "revisions",
            "titles": "|".join(sorted(titles)),
            "rvprop": "timestamp",
        },
    )
    return any(
        revision["timestamp"][:10] >= dump_date
        for page in body["query"]["pages"]
        for revision in page.get("revisions", [])
    )
