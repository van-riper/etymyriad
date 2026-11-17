"""Serialize etymology edges to and from the JSONL intermediate.

The `normalize` step writes edges here, plus a lone term for any entry
that produced none and each numbered section's claims, so the `load`
step can read them back without
re-parsing the dump. One JSON object per line keeps the file streamable.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from etymyriad.config import PROGRESS_LOG_INTERVAL
from etymyriad.datafiles import staged_path
from etymyriad.model import EtymEdge, SectionClaim, Term

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from etymyriad.model import GraphItem

_log = logging.getLogger(__name__)
_ENCODER = msgspec.json.Encoder()
_DECODER = msgspec.json.Decoder()


def item_to_json(item: GraphItem) -> bytes:
    """Serialize an edge, lone term, or section claim to one JSON line.

    Args:
        item: The item to serialize.

    Returns:
        One line of compact UTF-8 JSON, without its newline.
    """
    return _ENCODER.encode(item)


def _item_from_json(line: bytes) -> GraphItem:
    """Reconstruct an edge, a lone term, or a claim from one JSON line.

    Only an edge's JSON object has a "rel_type" key and only a claim's
    has a "listed" key, so those keys tell the three apart without a
    separate discriminator field.

    Args:
        line: A JSON object `write_edges` wrote.

    Returns:
        The reconstructed edge, term, or claim.
    """
    data = _DECODER.decode(line)
    if "rel_type" in data:
        return msgspec.convert(data, EtymEdge)
    if "listed" in data:
        return msgspec.convert(data, SectionClaim)
    return msgspec.convert(data, Term)


def write_edges(
    path: str | Path,
    edges: Iterable[GraphItem],
    *,
    log_every: int = PROGRESS_LOG_INTERVAL,
) -> int:
    """Write edges to a JSONL file, one per line.

    The file appears only once complete; a failed run leaves none.

    Args:
        path: Destination file path.
        edges: The etymology edges to write, plus the lone terms and
            section claims `normalize()` yielded.
        log_every: Emit an INFO progress log every this many edges, so a
            long normalize run stays visible in `tail -f` instead of going
            silent until it finishes. A final line logs the total when it
            is not a multiple of this.

    Returns:
        The number of lines written.
    """
    count = 0
    started_seconds = time.monotonic()
    with (
        staged_path(Path(path)) as staged,
        staged.open("wb") as handle,
    ):
        for item in edges:
            handle.write(item_to_json(item))
            handle.write(b"\n")
            count += 1
            if count % log_every == 0:
                _log_progress(count, started_seconds)
    if count % log_every:
        _log_progress(count, started_seconds)
    return count


def _log_progress(count: int, started_seconds: float) -> None:
    """Log the running line count and its rate since `started_seconds`."""
    items_per_second = count / (time.monotonic() - started_seconds)
    _log.info(
        "wrote %s edges (%s/sec)",
        f"{count:,}",
        f"{items_per_second:,.0f}",
    )


def read_edges(path: str | Path) -> Iterator[GraphItem]:
    """Stream edges from a JSONL file written by `write_edges`.

    Args:
        path: Source file path.

    Yields:
        One edge, lone term, or section claim per non-empty line.
    """
    with Path(path).open("rb") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield _item_from_json(stripped)
