"""Stream the Wiktextract dump into decoded entries.

kaikki.org distributes Wiktextract data as JSONL (one JSON object per line, one
per word sense), so we iterate line by line and never hold the whole file in
memory.
"""

from __future__ import annotations

import gzip
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from etymyriad.normalize import WiktextractEntry

if TYPE_CHECKING:
    from collections.abc import Iterator

_log = logging.getLogger(__name__)


def stream_entries(dump_path: str | Path) -> Iterator[WiktextractEntry]:
    """Stream decoded entries from a Wiktextract JSONL dump.

    Blank lines and page redirects are skipped. A line that isn't JSON,
    or an entry that names no word and language, is logged and skipped
    rather than aborting a run that can take over an hour against the
    full dump.
    Iteration is lazy, so the whole dump never lands in memory. A
    `.gz`-suffixed path is transparently decompressed.

    Args:
        dump_path: Path to the JSONL Wiktextract dump.

    Yields:
        One entry per valid, non-empty line.

    Raises:
        FileNotFoundError: If the dump path does not exist.
    """
    path = Path(dump_path)
    opener = gzip.open if path.suffix == ".gz" else Path.open
    try:
        handle = opener(path, mode="rt", encoding="utf-8")
    except FileNotFoundError as e:
        msg = f"Wiktextract dump not found: {path}"
        raise FileNotFoundError(msg) from e

    decoder = msgspec.json.Decoder(WiktextractEntry)
    with handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield decoder.decode(stripped)
            except msgspec.ValidationError as e:
                if _is_redirect(stripped):
                    continue
                _log.warning(
                    "skipping malformed entry at line %d: %s", line_number, e
                )
            except msgspec.DecodeError:
                _log.warning("skipping malformed JSONL at line %d", line_number)


def _is_redirect(line: str) -> bool:
    """Whether a line is a Wiktextract page redirect rather than an entry.

    A redirect looks like
    {"title": ..., "redirect": ..., "pos": "hard-redirect"}.

    Returns:
        True when the line decodes to an object with a "redirect" key.
    """
    record = msgspec.json.decode(line)
    return isinstance(record, dict) and "redirect" in record
