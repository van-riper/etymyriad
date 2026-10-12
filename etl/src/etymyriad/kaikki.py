"""Read which enwiktionary dump kaikki.org serves.

kaikki.org keeps only its latest dump, at an undated URL, and states that
dump's date on its download page. Citations name the date, so the ETL
reads it from there.
"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

from etymyriad.config import KAIKKI_RAWDATA_URL, USER_AGENT

if TYPE_CHECKING:
    import httpx

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
