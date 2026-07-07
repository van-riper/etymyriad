"""Serialize etymology edges to and from the JSONL intermediate.

The `normalize` step writes edges here so the `load` step can read them
back without re-parsing the dump. One JSON object per line keeps the file
streamable.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from etymyriad.model import EtymEdge, Lexeme, RelType

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


def edge_to_json(edge: EtymEdge) -> str:
    """Serialize an edge to a single JSON line.

    Args:
        edge: The etymology edge to serialize.

    Returns:
        A one-line JSON string (no embedded newlines).
    """
    return json.dumps(asdict(edge), ensure_ascii=False, sort_keys=True)


def edge_from_json(line: str) -> EtymEdge:
    """Reconstruct an edge from one JSON line.

    Args:
        line: A JSON object produced by `edge_to_json`.

    Returns:
        The reconstructed etymology edge.
    """
    data = json.loads(line)
    return EtymEdge(
        src=Lexeme(**data["src"]),
        dst=Lexeme(**data["dst"]),
        rel_type=RelType(data["rel_type"]),
        source_ref=data["source_ref"],
    )


def write_edges(path: str | Path, edges: Iterable[EtymEdge]) -> int:
    """Write edges to a JSONL file, one per line.

    Args:
        path: Destination file path.
        edges: The etymology edges to write.

    Returns:
        The number of edges written.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8") as handle:
        for edge in edges:
            handle.write(edge_to_json(edge))
            handle.write("\n")
            count += 1
    return count


def read_edges(path: str | Path) -> Iterator[EtymEdge]:
    """Stream edges from a JSONL file written by `write_edges`.

    Args:
        path: Source file path.

    Yields:
        One etymology edge per non-empty line.
    """
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield edge_from_json(stripped)
