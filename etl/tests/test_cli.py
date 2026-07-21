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


def test_filter_ine_writes_only_indo_european_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The filter-ine subcommand narrows a combined dump to IE languages."""
    dump = tmp_path / "combined.jsonl"
    dump.write_text(
        '{"word": "etymology", "lang": "English"}\n'
        '{"word": "水", "lang": "Japanese"}\n'
        '{"word": "aqua", "lang": "Latin"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "indo-european.jsonl"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["filter-ine", "--input", str(dump), "--output", str(out)])

    assert code == 0
    words = [json.loads(line)["word"] for line in out.read_text().splitlines()]
    assert words == ["etymology", "aqua"]


def test_normalize_writes_edge_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normalize subcommand streams the dump and writes an edge file."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        '{"word": "etymology", "lang_code": "en"}\n', encoding="utf-8"
    )
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


def test_load_prints_rel_type_breakdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The load subcommand reports edge counts broken down by rel_type."""
    edges_data = [
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
            dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
            rel_type=RelType.INHERITED,
            source_ref="w:e",
        ),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
            dst=Lexeme(lang_code="fr", headword="eau", source_ref="w:c"),
            rel_type=RelType.INHERITED,
            source_ref="w:f",
        ),
        EtymEdge(
            src=Lexeme(lang_code="en", headword="water", source_ref="w:g"),
            dst=Lexeme(lang_code="de", headword="Wasser", source_ref="w:h"),
            rel_type=RelType.COGNATE,
            source_ref="w:i",
        ),
    ]
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, edges_data)
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["load", "--edges", str(edges)])

    assert code == 0
    out = capsys.readouterr().out
    assert "inherited: 2" in out
    assert "cognate: 1" in out


def test_debug_flag_enables_debug_logging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--debug surfaces DEBUG-level log lines that are silent by default."""
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

    with caplog.at_level(logging.DEBUG):
        code = main(["--debug", "load", "--edges", str(edges)])

    assert code == 0
    assert "upserting" in caplog.text


def test_load_checkpoint_flag_persists_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """The --checkpoint flag writes progress usable by a later resume."""
    edge = EtymEdge(
        src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
        dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
        rel_type=RelType.INHERITED,
        source_ref="w:e",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [edge])
    checkpoint = tmp_path / "load.checkpoint"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main([
        "load",
        "--edges",
        str(edges),
        "--checkpoint",
        str(checkpoint),
    ])

    assert code == 0
    assert checkpoint.read_text() == "1"


def test_layout_subcommand_writes_positions_for_every_lexeme(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """`layout` computes and stores a position for every loaded lexeme."""
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
    assert main(["load", "--edges", str(edges)]) == 0

    code = main(["layout"])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        lexeme_count = conn.execute("SELECT count(*) FROM lexeme").fetchone()
        layout_count = conn.execute(
            "SELECT count(*) FROM lexeme_layout"
        ).fetchone()
    assert layout_count[0] == lexeme_count[0]


def test_all_subcommand_also_writes_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """`all` wires parse -> normalize -> load -> layout in one pass."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        '{"word": "frijaz", "lang_code": "gem-pro", "pos": "adj", '
        '"senses": [{"glosses": ["free"]}], '
        '"etymology_templates": [{"name": "inh", "args": '
        '{"1": "gem-pro", "2": "ine-pro", "3": "*priH\\u00f3s"}}]}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(dump))
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["all"])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        lexeme_count = conn.execute("SELECT count(*) FROM lexeme").fetchone()
        layout_count = conn.execute(
            "SELECT count(*) FROM lexeme_layout"
        ).fetchone()
    assert lexeme_count[0] > 0
    assert layout_count[0] == lexeme_count[0]
