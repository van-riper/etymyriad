"""Serialize etymology edges to and from the JSONL intermediate.

The `normalize` step writes edges here, plus a lone lexeme for any entry
that produced none, so the `load` step can read them back without
re-parsing the dump. One JSON object per line keeps the file streamable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from etymyriad.model import EtymEdge, Lexeme, RelType, Sense

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


def _lexeme_from_json(data: Mapping[str, Any]) -> Lexeme:
    """Rebuild a Lexeme from its JSON dict, restoring nested Sense objects.

    `asdict` flattens a Lexeme's `senses` tuple into a JSON array of plain
    dicts; a bare `Lexeme(**data)` would leave them as dicts instead of
    `Sense` instances, breaking round-trip equality.

    Args:
        data: A dict produced by `dataclasses.asdict` on a Lexeme, then
            JSON round-tripped.

    Returns:
        The reconstructed lexeme, with `senses` restored to `Sense` objects.
    """
    senses = tuple(Sense(**sense) for sense in data["senses"])
    return Lexeme(
        lang_code=data["lang_code"],
        headword=data["headword"],
        etymology_number=data["etymology_number"],
        romanization=data["romanization"],
        is_reconstructed=data["is_reconstructed"],
        source_ref=data["source_ref"],
        senses=senses,
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
        src=_lexeme_from_json(data["src"]),
        dst=_lexeme_from_json(data["dst"]),
        rel_type=RelType(data["rel_type"]),
        source_ref=data["source_ref"],
        piece_order=data["piece_order"],
    )


def lexeme_to_json(lexeme: Lexeme) -> str:
    """Serialize a lone lexeme (an entry with no edges of its own) to JSON.

    `normalize()` yields a bare Lexeme instead of an EtymEdge for an entry
    whose templates name no ancestor, so its senses still reach the load
    step.

    Args:
        lexeme: The lexeme to serialize.

    Returns:
        A one-line JSON string (no embedded newlines).
    """
    return json.dumps(asdict(lexeme), ensure_ascii=False, sort_keys=True)


def _item_from_json(line: str) -> EtymEdge | Lexeme:
    """Reconstruct an edge or a lone lexeme from one JSON line.

    An edge's JSON object has a "rel_type" key; a lone lexeme's never
    does, so that key's presence tells the two apart without a separate
    discriminator field.

    Args:
        line: A JSON object produced by `edge_to_json` or `lexeme_to_json`.

    Returns:
        The reconstructed edge or lexeme.
    """
    data = json.loads(line)
    if "rel_type" in data:
        return edge_from_json(line)
    return _lexeme_from_json(data)


def write_edges(
    path: str | Path,
    edges: Iterable[EtymEdge | Lexeme],
    *,
    log_every: int = 100_000,
) -> int:
    """Write edges to a JSONL file, one per line.

    Args:
        path: Destination file path.
        edges: The etymology edges to write, and any lone lexemes
            `normalize()` yielded for entries that produced no edges.
        log_every: Emit an INFO progress log every this many edges, so a
            long normalize run stays visible in `tail -f` instead of going
            silent until it finishes.

    Returns:
        The number of lines written.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8") as handle:
        for item in edges:
            line = (
                edge_to_json(item)
                if isinstance(item, EtymEdge)
                else lexeme_to_json(item)
            )
            handle.write(line)
            handle.write("\n")
            count += 1
            if count % log_every == 0:
                _log.info("wrote %s edges", f"{count:,}")
    return count


def read_edges(path: str | Path) -> Iterator[EtymEdge | Lexeme]:
    """Stream edges from a JSONL file written by `write_edges`.

    Args:
        path: Source file path.

    Yields:
        One edge or lone lexeme per non-empty line.
    """
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield _item_from_json(stripped)
