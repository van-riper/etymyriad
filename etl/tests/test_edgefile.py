"""Tests for the edge JSONL intermediate."""

import logging
from typing import TYPE_CHECKING

import pytest

from etymyriad.edgefile import read_edges, write_edges
from etymyriad.model import EtymEdge, RelType, SectionClaim, Sense, Term

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

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
_READING_CLAIM = SectionClaim(Term("ko", "마", section=7), reading="麻")


def test_round_trips_edges_terms_and_claims(tmp_path: Path) -> None:
    """Edges, lone terms, and section claims read back equal, in order."""
    path = tmp_path / "edges.jsonl"
    items = [_EDGE, _LONE, _ID_CLAIM, _LISTING_CLAIM, _READING_CLAIM]
    assert write_edges(path, items) == 5
    assert list(read_edges(path)) == items


def test_writes_compact_utf8_lines(tmp_path: Path) -> None:
    """Items are written without spaces or escaped non-ASCII."""
    path = tmp_path / "edges.jsonl"
    write_edges(path, [Term("grc", "ἄκρος")])
    assert path.read_text(encoding="utf-8") == (
        '{"lang_code":"grc","headword":"ἄκρος","section":0,'
        '"is_reconstructed":false,"variety_code":null,"senses":[],'
        '"redirect_headword":null}\n'
    )


def test_reads_an_edge_file_with_sorted_spaced_keys(tmp_path: Path) -> None:
    """A file from before the compact format still reads back."""
    path = tmp_path / "edges.jsonl"
    path.write_text(
        '{"headword": "or", "is_reconstructed": false, "lang_code": "enm", '
        '"section": 1, "senses": [], "variety_code": null}\n'
        '{"listed": {"headword": "or", "is_reconstructed": false, '
        '"lang_code": "en", "section": 0, "senses": [], '
        '"variety_code": null}, "term": {"headword": "or", '
        '"is_reconstructed": false, "lang_code": "enm", "section": 1, '
        '"senses": [{"gloss": "gold", "part_of_speech": "noun"}], '
        '"variety_code": null}, "wiktionary_id": null}\n',
        encoding="utf-8",
    )
    assert list(read_edges(path)) == [
        Term("enm", "or", section=1),
        SectionClaim(
            Term("enm", "or", section=1, senses=(Sense("noun", "gold"),)),
            listed=Term("en", "or"),
        ),
    ]


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


def test_write_edges_leaves_no_temp_file(tmp_path: Path) -> None:
    """A finished write leaves only the edge file."""
    path = tmp_path / "edges.jsonl"
    write_edges(path, [_EDGE])
    assert [child.name for child in tmp_path.iterdir()] == ["edges.jsonl"]


def test_write_edges_leaves_nothing_when_the_stream_raises(
    tmp_path: Path,
) -> None:
    """A normalize that dies mid-stream leaves no partial edge file."""

    def _items() -> Iterator[EtymEdge]:
        yield _EDGE
        msg = "normalize died"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="normalize died"):
        write_edges(tmp_path / "edges.jsonl", _items())
    assert list(tmp_path.iterdir()) == []
