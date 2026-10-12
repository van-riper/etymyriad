"""Tests for reading the served dump date off kaikki.org."""

from __future__ import annotations

import httpx
import pytest

from etymyriad.config import USER_AGENT
from etymyriad.kaikki import served_dump_date

_PAGE = (
    "<p>This data is based on structured data extracted on 2026-10-03 "
    "from the enwiktionary dump dated 2026-09-02 using "
    '<a href="https://github.com/tatuylonen/wiktextract">wiktextract</a>.'
    "</p>"
)


def _kaikki(
    page: str, status_code: int = 200
) -> tuple[httpx.Client, list[httpx.Request]]:
    """Fake kaikki.org's download page.

    Returns:
        The client, and the list each request it sends is appended to.
    """
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status_code, text=page)

    return httpx.Client(transport=httpx.MockTransport(handle)), requests


def test_reads_the_dump_date_not_the_extraction_date() -> None:
    """The page names two dates; citations need the enwiktionary one."""
    client, requests = _kaikki(_PAGE)

    assert served_dump_date(client) == "2026-09-02"

    (request,) = requests
    assert request.url == "https://kaikki.org/dictionary/rawdata.html"
    assert request.headers["User-Agent"] == USER_AGENT


def test_a_page_without_a_dump_date_raises() -> None:
    """A reworded page fails loudly instead of citing a wrong date."""
    client, _ = _kaikki("<p>Downloads are temporarily unavailable.</p>")

    with pytest.raises(ValueError, match="names no enwiktionary dump date"):
        served_dump_date(client)


def test_an_impossible_dump_date_raises() -> None:
    """A date Postgres would reject is caught before the load starts."""
    client, _ = _kaikki("from the enwiktionary dump dated 2026-13-01 using")

    with pytest.raises(ValueError, match="impossible dump date 2026-13-01"):
        served_dump_date(client)


def test_a_server_error_raises() -> None:
    """A 5xx page is an error, not a page with no date on it."""
    client, _ = _kaikki(_PAGE, status_code=503)

    with pytest.raises(httpx.HTTPStatusError):
        served_dump_date(client)


def test_follows_a_redirect_to_the_page() -> None:
    """CI reads the page with `curl -L`, so a moved page must still work."""
    moved_to = "https://kaikki.org/dictionary/moved.html"

    def handle(request: httpx.Request) -> httpx.Response:
        if str(request.url) == moved_to:
            return httpx.Response(200, text=_PAGE)
        return httpx.Response(301, headers={"Location": moved_to})

    client = httpx.Client(transport=httpx.MockTransport(handle))

    assert served_dump_date(client) == "2026-09-02"
