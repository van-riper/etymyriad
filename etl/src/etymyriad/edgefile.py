"""Serialize etymology edges to and from the JSONL intermediate.

The `normalize` step writes edges here, plus a lone term for any entry
that produced none and each numbered section's claims, so the `load`
step can read them back without
re-parsing the dump. One JSON object per line keeps the file streamable.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from etymyriad.model import EtymEdge, RelType, SectionClaim, Sense, Term

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from typing import Any

    from etymyriad.model import GraphItem

_log = logging.getLogger(__name__)


def item_to_json(item: GraphItem) -> str:
    """Serialize an edge, lone term, or section claim to one JSON line.

    Args:
        item: The item to serialize.

    Returns:
        A one-line JSON string (no embedded newlines).
    """
    return json.dumps(asdict(item), ensure_ascii=False, sort_keys=True)


def _term_from_json(data: Mapping[str, Any]) -> Term:
    """Rebuild a Term from its JSON dict, restoring nested Sense objects.

    Args:
        data: A dict produced by `dataclasses.asdict` on a Term.

    Returns:
        The reconstructed term.
    """
    return Term(
        lang_code=data["lang_code"],
        headword=data["headword"],
        section=data["section"],
        is_reconstructed=data["is_reconstructed"],
        variety_code=data["variety_code"],
        senses=tuple(Sense(**sense) for sense in data["senses"]),
    )


def edge_from_json(line: str) -> EtymEdge:
    """Reconstruct an edge from one JSON line.

    Args:
        line: An edge's JSON object, as `item_to_json` writes it.

    Returns:
        The reconstructed etymology edge.
    """
    data = json.loads(line)
    return EtymEdge(
        src=_term_from_json(data["src"]),
        dst=_term_from_json(data["dst"]),
        rel_type=RelType(data["rel_type"]),
        anchor=data["anchor"],
        piece_order=data["piece_order"],
        src_wiktionary_id=data["src_wiktionary_id"],
    )


def _claim_from_json(data: Mapping[str, Any]) -> SectionClaim:
    """Rebuild a SectionClaim from its JSON dict.

    Args:
        data: A dict produced by `dataclasses.asdict` on a SectionClaim.

    Returns:
        The reconstructed claim.
    """
    listed = data["listed"]
    return SectionClaim(
        term=_term_from_json(data["term"]),
        wiktionary_id=data["wiktionary_id"],
        listed=_term_from_json(listed) if listed is not None else None,
    )


def _item_from_json(line: str) -> GraphItem:
    """Reconstruct an edge, a lone term, or a claim from one JSON line.

    Only an edge's JSON object has a "rel_type" key and only a claim's
    has a "listed" key, so those keys tell the three apart without a
    separate discriminator field.

    Args:
        line: A JSON object `write_edges` wrote.

    Returns:
        The reconstructed edge, term, or claim.
    """
    data = json.loads(line)
    if "rel_type" in data:
        return edge_from_json(line)
    if "listed" in data:
        return _claim_from_json(data)
    return _term_from_json(data)


def write_edges(
    path: str | Path,
    edges: Iterable[GraphItem],
    *,
    log_every: int = 100_000,
) -> int:
    """Write edges to a JSONL file, one per line.

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
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    started_seconds = time.monotonic()
    with out.open("w", encoding="utf-8") as handle:
        for item in edges:
            handle.write(item_to_json(item))
            handle.write("\n")
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
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield _item_from_json(stripped)
