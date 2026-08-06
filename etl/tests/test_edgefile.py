"""Tests for the edge JSONL intermediate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from etymyriad.edgefile import (
    edge_from_json,
    edge_to_json,
    read_edges,
    write_edges,
)
from etymyriad.model import EtymEdge, Lexeme, RelType, Sense

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_edge_survives_json_round_trip() -> None:
    """Serializing an edge and reading it back yields an equal edge.

    dst carries a Sense (pos), which round-trips through JSON as a nested
    dict unless edge_from_json rebuilds it back into a Sense object.
    """
    edge = EtymEdge(
        src=Lexeme(
            lang_code="ine-pro",
            headword="ph₂tḗr",
            is_reconstructed=True,
            source_ref="wiktionary:2026-06-01:ine-pro:ph₂tḗr",
        ),
        dst=Lexeme(
            lang_code="en",
            headword="father",
            source_ref="wiktionary:2026-06-01:en:father",
            senses=(
                Sense(
                    pos="noun",
                    source_ref="wiktionary:2026-06-01:en:father",
                ),
            ),
        ),
        rel_type=RelType.INHERITED,
        source_ref="wiktionary:2026-06-01:edge",
    )
    assert edge_from_json(edge_to_json(edge)) == edge


def test_edge_piece_order_survives_json_round_trip() -> None:
    """A non-null piece_order (e.g. an affix piece) round-trips too."""
    edge = EtymEdge(
        src=Lexeme(lang_code="en", headword="un-", source_ref="w:a"),
        dst=Lexeme(lang_code="en", headword="unhappy", source_ref="w:b"),
        rel_type=RelType.AFFIX,
        source_ref="w:e",
        piece_order=1,
    )
    assert edge_from_json(edge_to_json(edge)) == edge


def test_edge_json_is_a_single_line() -> None:
    """A serialized edge is one line, so the intermediate stays JSONL."""
    edge = EtymEdge(
        src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
        dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
        rel_type=RelType.INHERITED,
        source_ref="w:e",
    )
    assert "\n" not in edge_to_json(edge)


def test_write_then_read_edges_round_trip(tmp_path: Path) -> None:
    """Edges written to a file read back equal, in order."""
    edges = [
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
            dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
            rel_type=RelType.INHERITED,
            source_ref="w:e1",
        ),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
            dst=Lexeme(lang_code="fr", headword="eau", source_ref="w:c"),
            rel_type=RelType.INHERITED,
            source_ref="w:e2",
        ),
    ]
    path = tmp_path / "edges.jsonl"

    written = write_edges(path, iter(edges))

    assert written == 2
    assert list(read_edges(path)) == edges


def test_write_edges_logs_progress_periodically(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """write_edges logs every `log_every` edges.

    So a long ETL run shows up in `tail -f` instead of going silent
    until it finishes.
    """
    edges = [
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
            dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
            rel_type=RelType.INHERITED,
            source_ref=f"w:e{i}",
        )
        for i in range(3)
    ]
    path = tmp_path / "edges.jsonl"

    with caplog.at_level(logging.INFO, logger="etymyriad.edgefile"):
        write_edges(path, iter(edges), log_every=2)

    progress_logs = [r for r in caplog.records if "2" in r.message]
    assert len(progress_logs) == 1
