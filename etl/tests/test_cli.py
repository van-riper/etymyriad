"""Tests for the command-line entry point."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import psycopg

from etymyriad.__main__ import main
from etymyriad.edgefile import write_edges
from etymyriad.model import EtymEdge, Lexeme, RelType

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_load_failure_redacts_dsn_from_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed load logs its error without leaking the DSN password.

    Driver errors (e.g. a bad conninfo string) sometimes echo the DSN
    verbatim in their message; that must never reach a log unredacted.
    """
    dsn = "postgresql://etymyriad:s3cret@db.neon.tech/main"
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    def _boom(*_args: object, **_kwargs: object) -> int:
        msg = f"connection failed: {dsn}"
        raise psycopg.OperationalError(msg)

    monkeypatch.setattr("etymyriad.__main__.load_edges", _boom)

    with caplog.at_level(logging.ERROR):
        code = main(["load", "--edges", str(edges)])

    assert code == 1
    assert "s3cret" not in caplog.text


def test_filter_ie_writes_only_indo_european_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The filter-ie subcommand narrows a combined dump to IE languages."""
    dump = tmp_path / "combined.jsonl"
    dump.write_text(
        '{"word": "water", "lang": "English"}\n'
        '{"word": "水", "lang": "Japanese"}\n'
        '{"word": "aqua", "lang": "Latin"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "indo-european.jsonl"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["filter-ie", "--input", str(dump), "--output", str(out)])

    assert code == 0
    words = [json.loads(line)["word"] for line in out.read_text().splitlines()]
    assert words == ["water", "aqua"]


def test_normalize_writes_edge_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normalize subcommand streams the dump and writes an edge file."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text('{"word": "water", "lang_code": "en"}\n', encoding="utf-8")
    edges = tmp_path / "edges.jsonl"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(dump))
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["normalize", "--edges", str(edges)])

    assert code == 0
    assert edges.exists()


def test_load_inserts_edges_from_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """The load subcommand reads an edge file and inserts it into Postgres."""
    edge = EtymEdge(
        src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
        dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
        rel_type=RelType.INHERITED,
        source_ref="w:e",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [edge])
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["load", "--edges", str(edges)])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        edge_count = conn.execute("SELECT count(*) FROM etymology").fetchone()
    assert edge_count is not None
    assert edge_count[0] == 1
