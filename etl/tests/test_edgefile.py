"""Tests for the edge JSONL intermediate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from etymyriad.edgefile import read_edges, write_edges
from etymyriad.model import EtymEdge, RelType, Sense, Term

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_EDGE = EtymEdge(
    src=Term("la", "aqua", variety_code="la-lat", is_reconstructed=False),
    dst=Term(
        "en",
        "aqua",
        section=2,
        senses=(Sense(part_of_speech="noun", gloss="water"),),
    ),
    rel_type=RelType.BORROWED,
    anchor="etymology_templates:0:bor",
    piece_order=None,
)
_LONE = Term("en", "onomatopoeia", senses=(Sense("noun", "a word"),))


def test_round_trips_edges_and_lone_terms(tmp_path: Path) -> None:
    """Edges and lone terms read back equal, in order."""
    path = tmp_path / "edges.jsonl"
    assert write_edges(path, [_EDGE, _LONE]) == 2
    assert list(read_edges(path)) == [_EDGE, _LONE]


def test_write_edges_logs_progress_periodically(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """write_edges logs once per `log_every` lines written."""
    path = tmp_path / "edges.jsonl"

    with caplog.at_level(logging.INFO, logger="etymyriad.edgefile"):
        write_edges(path, [_EDGE] * 3, log_every=2)

    assert len([r for r in caplog.records if "2" in r.message]) == 1
