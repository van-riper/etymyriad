"""Stream the Wiktextract dump into raw entry dicts.

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

if TYPE_CHECKING:
    from collections.abc import Iterator

_log = logging.getLogger(__name__)


def stream_entries(dump_path: str | Path) -> Iterator[dict[str, object]]:
    """Stream parsed JSON objects from a Wiktextract JSONL dump.

    Blank lines are skipped. A line that fails to decode is logged and
    skipped rather than aborting the stream. Iteration is lazy, so the
    whole dump never lands in memory. A `.gz`-suffixed path is
    transparently decompressed.

    Args:
        dump_path: Path to the JSONL Wiktextract dump.

    Yields:
        One decoded JSON object per valid, non-empty line.

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

    decoder = msgspec.json.Decoder()
    with handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield decoder.decode(stripped)
            except msgspec.DecodeError:
                _log.warning("skipping malformed JSONL at line %d", line_number)
