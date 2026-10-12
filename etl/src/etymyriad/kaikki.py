"""Read which enwiktionary dump kaikki.org serves.

kaikki.org keeps only its latest dump, at an undated URL, and states that
dump's date on its download page. Citations name the date, so the ETL
reads it from there.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from time import monotonic
from typing import TYPE_CHECKING

import httpx

from etymyriad import datafiles
from etymyriad.config import (
    DUMP_DOWNLOAD_ATTEMPTS,
    DUMP_PROGRESS_INTERVAL_SECONDS,
    KAIKKI_RAW_DUMP_URL,
    KAIKKI_RAWDATA_URL,
    USER_AGENT,
)

if TYPE_CHECKING:
    from pathlib import Path

_log = logging.getLogger(__name__)

_DUMP_DATE = re.compile(r"enwiktionary dump dated (\d{4}-\d{2}-\d{2})")


def served_dump_date(client: httpx.Client) -> str:
    """Read the date of the enwiktionary dump kaikki.org serves now.

    Args:
        client: The HTTP client to use.

    Returns:
        The dump's date, as YYYY-MM-DD.

    Raises:
        ValueError: If the page names no dump date, or one that doesn't
            exist.
    """
    response = client.get(
        KAIKKI_RAWDATA_URL,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )
    response.raise_for_status()
    match = _DUMP_DATE.search(response.text)
    if match is None:
        msg = f"{KAIKKI_RAWDATA_URL} names no enwiktionary dump date"
        raise ValueError(msg)
    served = match.group(1)
    try:
        date.fromisoformat(served)
    except ValueError as e:
        msg = f"{KAIKKI_RAWDATA_URL} names an impossible dump date {served}"
        raise ValueError(msg) from e
    return served


def _format_size(size_bytes: int) -> str:
    """Format a byte count with the largest unit that keeps it above one.

    Args:
        size_bytes: The size to format.

    Returns:
        The size with its unit, such as "1.5 MiB".
    """
    size = float(size_bytes)
    for unit in ("B", "KiB", "MiB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.2f} GiB"


def download_raw_dump(client: httpx.Client, destination: Path) -> None:
    """Download the raw enwiktionary dump kaikki.org serves now.

    The file appears at `destination` only once it is complete. A read
    timeout restarts the download, up to `DUMP_DOWNLOAD_ATTEMPTS` tries.

    Args:
        client: The HTTP client to use.
        destination: Where to put the dump.

    Raises:
        httpx.ReadTimeout: If every attempt timed out.
    """
    for attempt in range(1, DUMP_DOWNLOAD_ATTEMPTS + 1):
        try:
            _download_once(client, destination)
        except httpx.ReadTimeout:
            if attempt == DUMP_DOWNLOAD_ATTEMPTS:
                raise
            _log.warning(
                "download timed out (attempt %d of %d); retrying",
                attempt,
                DUMP_DOWNLOAD_ATTEMPTS,
            )
        else:
            return


def _download_once(client: httpx.Client, destination: Path) -> None:
    """Stream the raw dump to `destination`.

    Args:
        client: The HTTP client to use.
        destination: Where to put the dump.
    """
    with (
        datafiles.staged_path(destination) as staged,
        client.stream(
            "GET",
            KAIKKI_RAW_DUMP_URL,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as response,
        staged.open("wb") as handle,
    ):
        response.raise_for_status()
        total_bytes = int(response.headers.get("Content-Length", 0))
        _log.info(
            "downloading the raw dump (%s)",
            _format_size(total_bytes) if total_bytes else "size unknown",
        )
        last_report_seconds = monotonic()
        for chunk in response.iter_bytes():
            handle.write(chunk)
            now_seconds = monotonic()
            if (
                now_seconds - last_report_seconds
                < DUMP_PROGRESS_INTERVAL_SECONDS
            ):
                continue
            last_report_seconds = now_seconds
            downloaded_bytes = response.num_bytes_downloaded
            if total_bytes:
                _log.info(
                    "downloaded %s of %s (%d%%)",
                    _format_size(downloaded_bytes),
                    _format_size(total_bytes),
                    downloaded_bytes * 100 // total_bytes,
                )
            else:
                _log.info("downloaded %s", _format_size(downloaded_bytes))
    _log.info(
        "downloaded the raw dump (%s)",
        _format_size(response.num_bytes_downloaded),
    )
