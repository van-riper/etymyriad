"""Tests for pulling the tree JSON out of a rendered Wiktionary page."""

import httpx

from etymyriad.crosscheck import (
    edited_after_dump,
    extract_tree,
    fetch_tree,
)

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


def _wiktionary(
    revisions: list[dict[str, int]], page_html: str
) -> tuple[httpx.Client, list[httpx.Request]]:
    """Fake the two API calls: the revision lookup, then the parse.

    Returns:
        The client, and the list each request it sends is appended to.
    """
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params["action"] == "query":
            page = {"title": "wine", "revisions": revisions}
            return httpx.Response(200, json={"query": {"pages": [page]}})
        return httpx.Response(200, json={"parse": {"text": page_html}})

    return httpx.Client(transport=httpx.MockTransport(handle)), requests


def test_fetch_parses_the_revision_current_on_the_dump_date() -> None:
    """A page edited after the dump must not count against the parser."""
    client, requests = _wiktionary(
        [{"revid": 123}], _ONE_TREE.format(lang="en", term="wine")
    )

    tree = fetch_tree(client, "wine", "en", "2026-09-02")

    lookup, parse = requests
    assert lookup.url.params["rvstart"] == "2026-09-02T23:59:59Z"
    assert lookup.url.params["rvdir"] == "older"
    assert parse.url.params["oldid"] == "123"
    assert tree == {"term": "wine"}


def test_fetch_returns_none_for_a_page_created_after_the_dump() -> None:
    """No revision on or before the dump date means nothing to compare."""
    client, requests = _wiktionary([], _ONE_TREE.format(lang="en", term="wine"))

    assert fetch_tree(client, "wine", "en", "2026-09-02") is None
    assert len(requests) == 1


def _latest_revisions(
    timestamps: dict[str, str],
) -> tuple[httpx.Client, list[httpx.Request]]:
    """Fake a latest-revision lookup over the given pages.

    Returns:
        The client, and the list each request it sends is appended to.
    """
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        pages = [
            {"title": title, "revisions": [{"timestamp": timestamps[title]}]}
            if title in timestamps
            else {"title": title, "missing": True}
            for title in request.url.params["titles"].split("|")
        ]
        return httpx.Response(200, json={"query": {"pages": pages}})

    return httpx.Client(transport=httpx.MockTransport(handle)), requests


def test_page_edited_on_the_dump_day_counts_as_edited() -> None:
    """The dump is taken partway through its day; it may lack the edit."""
    client, _ = _latest_revisions({"vinum": "2026-10-01T17:22:31Z"})
    assert edited_after_dump(client, "la", "vīnum", "2026-10-01")


def test_page_untouched_since_before_the_dump_is_not_edited() -> None:
    """A page whose last edit predates the dump renders as dumped."""
    client, _ = _latest_revisions({"vinum": "2026-09-30T23:59:59Z"})
    assert not edited_after_dump(client, "la", "vīnum", "2026-10-01")


def test_lookup_tries_the_term_with_and_without_marks() -> None:
    """Trees show diacritics some page titles drop, and keep others."""
    client, requests = _latest_revisions({"οἶνος": "2026-11-01T00:00:00Z"})
    assert edited_after_dump(client, "grc", "οἶνος", "2026-10-01")
    assert set(requests[0].url.params["titles"].split("|")) == {
        "οἶνος",
        "οινος",
    }


def test_missing_page_is_not_edited() -> None:
    """A term with no page of its own has no edit to blame."""
    client, _ = _latest_revisions({})
    assert not edited_after_dump(client, "gem-pro", "*wīną", "2026-10-01")


def test_reconstruction_is_looked_up_under_its_namespace() -> None:
    """A starred term's page lives at Reconstruction:<language>/<term>."""
    title = "Reconstruction:Proto-Indo-European/-yós"
    client, requests = _latest_revisions({title: "2026-11-05T07:14:06Z"})
    assert edited_after_dump(client, "ine-pro", "*-yós", "2026-10-01")
    assert set(requests[0].url.params["titles"].split("|")) == {
        title,
        "Reconstruction:Proto-Indo-European/-yos",
    }


def test_reconstruction_in_an_unknown_language_is_not_edited() -> None:
    """With no language name there is no Reconstruction title to ask."""
    client, requests = _latest_revisions({})
    assert not edited_after_dump(client, "xx-unknown", "*foo", "2026-10-01")
    assert requests == []
