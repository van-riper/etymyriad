"""Serialize etymology edges to and from the JSONL intermediate.

The `normalize` step writes edges here, plus a lone term for any entry
that produced none, so the `load` step can read them back without
re-parsing the dump. One JSON object per line keeps the file streamable.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from etymyriad.model import EtymEdge, RelType, Sense, Term

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from typing import Any

_log = logging.getLogger(__name__)


def edge_to_json(edge: EtymEdge) -> str:
    """Serialize an edge to a single JSON line.

    Args:
        edge: The etymology edge to serialize.

    Returns:
        A one-line JSON string (no embedded newlines).
    """
    return json.dumps(asdict(edge), ensure_ascii=False, sort_keys=True)


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
        line: A JSON object produced by `edge_to_json`.

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
    )


def term_to_json(term: Term) -> str:
    """Serialize a lone term (an entry with no edges of its own) to JSON.

    `normalize()` yields a bare Term instead of an EtymEdge for an entry
    whose templates name no ancestor, so its senses still reach the load
    step.

    Args:
        term: The term to serialize.

    Returns:
        A one-line JSON string (no embedded newlines).
    """
    return json.dumps(asdict(term), ensure_ascii=False, sort_keys=True)


def _item_from_json(line: str) -> EtymEdge | Term:
    """Reconstruct an edge or a lone term from one JSON line.

    An edge's JSON object has a "rel_type" key; a lone term's never
    does, so that key's presence tells the two apart without a separate
    discriminator field.

    Args:
        line: A JSON object produced by `edge_to_json` or `term_to_json`.

    Returns:
        The reconstructed edge or term.
    """
    data = json.loads(line)
    if "rel_type" in data:
        return edge_from_json(line)
    return _term_from_json(data)


def write_edges(
    path: str | Path,
    edges: Iterable[EtymEdge | Term],
    *,
    log_every: int = 100_000,
) -> int:
    """Write edges to a JSONL file, one per line.

    Args:
        path: Destination file path.
        edges: The etymology edges to write, and any lone terms
            `normalize()` yielded for entries that produced no edges.
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
            line = (
                edge_to_json(item)
                if isinstance(item, EtymEdge)
                else term_to_json(item)
            )
            handle.write(line)
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


def read_edges(path: str | Path) -> Iterator[EtymEdge | Term]:
    """Stream edges from a JSONL file written by `write_edges`.

    Args:
        path: Source file path.

    Yields:
        One edge or lone term per non-empty line.
    """
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield _item_from_json(stripped)
