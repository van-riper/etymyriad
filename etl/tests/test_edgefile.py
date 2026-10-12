"""Tests for the edge JSONL intermediate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from etymyriad.edgefile import read_edges, write_edges
from etymyriad.model import EtymEdge, RelType, SectionClaim, Sense, Term

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
    src_wiktionary_id="water",
)
_LONE = Term("en", "onomatopoeia", senses=(Sense("noun", "a word"),))
_ID_CLAIM = SectionClaim(Term("en", "or", section=3), wiktionary_id="gold")
_LISTING_CLAIM = SectionClaim(
    Term("enm", "or", section=1), listed=Term("en", "or")
)


def test_round_trips_edges_terms_and_claims(tmp_path: Path) -> None:
    """Edges, lone terms, and section claims read back equal, in order."""
    path = tmp_path / "edges.jsonl"
    items = [_EDGE, _LONE, _ID_CLAIM, _LISTING_CLAIM]
    assert write_edges(path, items) == 4
    assert list(read_edges(path)) == items


def test_write_edges_logs_progress_periodically(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """write_edges logs once per `log_every` lines written."""
    path = tmp_path / "edges.jsonl"

    with caplog.at_level(logging.INFO, logger="etymyriad.edgefile"):
        write_edges(path, [_EDGE] * 3, log_every=2)

    assert [r.message.split(" (")[0] for r in caplog.records] == [
        "wrote 2 edges",
        "wrote 3 edges",
    ]


def test_write_edges_does_not_repeat_a_final_periodic_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A total that lands on `log_every` is logged once, not twice."""
    with caplog.at_level(logging.INFO, logger="etymyriad.edgefile"):
        write_edges(tmp_path / "edges.jsonl", [_EDGE] * 4, log_every=2)

    assert len(caplog.records) == 2


def test_write_edges_progress_log_includes_a_rate(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The progress line shows items per second since the start."""
    clock = iter([0.0, 0.5])
    monkeypatch.setattr(
        "etymyriad.edgefile.time.monotonic", lambda: next(clock)
    )

    with caplog.at_level(logging.INFO, logger="etymyriad.edgefile"):
        write_edges(tmp_path / "edges.jsonl", [_EDGE] * 2, log_every=2)

    assert "wrote 2 edges (4/sec)" in caplog.text
