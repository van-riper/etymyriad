"""Tests for reading the served dump date off kaikki.org."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
import pytest

from etymyriad.config import USER_AGENT
from etymyriad.kaikki import download_raw_dump, served_dump_date

if TYPE_CHECKING:
    from pathlib import Path

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


def test_download_raw_dump_writes_the_body_to_the_destination(
    tmp_path: Path,
) -> None:
    """The dump lands at the destination, fetched with our User-Agent."""
    client, requests = _kaikki("dump bytes")
    destination = tmp_path / "data" / "wiktextract-data-2026-09-02.jsonl.gz"

    download_raw_dump(client, destination)

    assert destination.read_text(encoding="utf-8") == "dump bytes"
    (request,) = requests
    assert str(request.url) == (
        "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"
    )
    assert request.headers["User-Agent"] == USER_AGENT


def test_a_failed_download_leaves_no_file(tmp_path: Path) -> None:
    """A 5xx raises and leaves neither the dump nor a partial temp file."""
    client, _ = _kaikki("oops", status_code=503)
    destination = tmp_path / "wiktextract-data-2026-09-02.jsonl.gz"

    with pytest.raises(httpx.HTTPStatusError):
        download_raw_dump(client, destination)

    assert list(tmp_path.iterdir()) == []


def _timing_out_then_serving(
    timeouts: int, body: bytes
) -> tuple[httpx.Client, list[httpx.Request]]:
    """Fake a dump whose first requests time out mid-read.

    Returns:
        The client, and the list each request it sends is appended to.
    """
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) <= timeouts:
            msg = "stalled"
            raise httpx.ReadTimeout(msg, request=request)
        return httpx.Response(200, content=body)

    return httpx.Client(transport=httpx.MockTransport(handle)), requests


def test_a_read_timeout_is_retried(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A stalled stream restarts the download instead of failing the run."""
    client, requests = _timing_out_then_serving(1, b"dump bytes")
    destination = tmp_path / "dump.jsonl.gz"

    with caplog.at_level(logging.WARNING, logger="etymyriad.kaikki"):
        download_raw_dump(client, destination)

    assert destination.read_bytes() == b"dump bytes"
    assert len(requests) == 2
    assert [record.getMessage() for record in caplog.records] == [
        "download timed out (attempt 1 of 3); retrying"
    ]


def test_a_read_timeout_on_every_attempt_raises(tmp_path: Path) -> None:
    """Retries are bounded, and a final timeout leaves no file."""
    client, requests = _timing_out_then_serving(99, b"")

    with pytest.raises(httpx.ReadTimeout):
        download_raw_dump(client, tmp_path / "dump.jsonl.gz")

    assert len(requests) == 3
    assert list(tmp_path.iterdir()) == []


def _chunked_dump(
    chunks: list[bytes], content_length: int | None
) -> httpx.Client:
    """Fake a dump served in chunks, with or without a Content-Length.

    Returns:
        A client whose every request gets the chunked dump.
    """
    headers = {}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)

    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=headers, content=iter(chunks))

    return httpx.Client(transport=httpx.MockTransport(handle))


def _fake_clock(
    monkeypatch: pytest.MonkeyPatch, readings_seconds: list[float]
) -> None:
    """Make the download read these times, one per clock call."""
    readings = iter(readings_seconds)
    monkeypatch.setattr("etymyriad.kaikki.monotonic", lambda: next(readings))


def test_download_logs_progress_against_the_known_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Each elapsed interval logs the bytes so far and the percent done."""
    monkeypatch.setattr("etymyriad.kaikki.DUMP_PROGRESS_INTERVAL_SECONDS", 10)
    _fake_clock(monkeypatch, [0, 5, 11, 15, 22])
    client = _chunked_dump([b"aaaa", b"bbbb", b"cc", b"dd"], content_length=12)

    with caplog.at_level(logging.INFO, logger="etymyriad.kaikki"):
        download_raw_dump(client, tmp_path / "dump.jsonl.gz")

    assert [record.getMessage() for record in caplog.records] == [
        "downloading the raw dump (12 B)",
        "downloaded 8 B of 12 B (66%)",
        "downloaded 12 B of 12 B (100%)",
        "downloaded the raw dump (12 B)",
    ]


def test_download_logs_progress_without_a_known_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With no Content-Length the log still shows bytes so far."""
    monkeypatch.setattr("etymyriad.kaikki.DUMP_PROGRESS_INTERVAL_SECONDS", 10)
    _fake_clock(monkeypatch, [0, 11, 12])
    client = _chunked_dump([b"aaaa", b"bb"], content_length=None)

    with caplog.at_level(logging.INFO, logger="etymyriad.kaikki"):
        download_raw_dump(client, tmp_path / "dump.jsonl.gz")

    assert [record.getMessage() for record in caplog.records] == [
        "downloading the raw dump (size unknown)",
        "downloaded 4 B",
        "downloaded the raw dump (6 B)",
    ]
